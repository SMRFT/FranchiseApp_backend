import os
import json
import csv
import calendar
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from bson.decimal128 import Decimal128
from django.utils import timezone
from .models import Billing, PaymentTransaction

def to_decimal(val):
    """Convert Mongo Decimal128 or other numeric types/strings (even with smart quotes) to Decimal."""
    if val is None:
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val
    if isinstance(val, Decimal128):
        return val.to_decimal()

    s = str(val)
    # remove smart quotes & normal quotes
    s = (
        s.replace('“', '')
         .replace('”', '')
         .replace('"', '')
         .replace("'", '')
         .strip()
    )
    try:
        return Decimal(s)
    except Exception:
        return Decimal('0.00')


@api_view(['PUT'])
def update_due_amount(request):
    barcode = request.data.get('barcode')
    paid_amount = request.data.get('paid_amount')  # amount being paid now
    payment_mode = request.data.get('payment_mode', 'Cash')
    remarks = request.data.get('remarks', 'Due Clearance')

    if not barcode or paid_amount is None:
        return Response({"error": "Barcode and paid_amount are required"}, status=400)

    try:
        billing = Billing.objects.get(barcode=barcode)

        # Convert values for calculation ONLY (do not assign back to model)
        net_amount = to_decimal(billing.netAmount)
        current_paid = to_decimal(getattr(billing, 'billed_amount', None))
        payment_amount = to_decimal(paid_amount)

        if payment_amount <= 0:
            return Response({"error": "Paid amount must be greater than zero"}, status=400)

        # New total paid
        new_total_paid = current_paid + payment_amount
        print("payment_amount",payment_amount)
        print("net_amount",net_amount)
        # ❗ Fix logic: cannot exceed total bill
        if payment_amount > net_amount:
            remaining = net_amount - current_paid
            return Response(
                {
                    "error": "Paid amount cannot exceed total bill amount",
                    "remaining_allowed": str(remaining)
                },
                status=400
            )

        # Compute new due (for response)
        new_due = net_amount - new_total_paid

        # Update billing using .update() to avoid validating other dirty decimal fields
        
        # Prepare new payment entry
        new_payment_entry = {
            "amount": float(payment_amount),
            "mode": payment_mode,
            "date": timezone.now().isoformat(),
            "remarks": remarks
        }
        
        # Fetch current payments list safely
        current_payments = billing.payments
        if isinstance(current_payments, str):
            try:
                current_payments = json.loads(current_payments)
            except Exception:
                current_payments = []
        elif not isinstance(current_payments, list):
            current_payments = []

        current_payments.append(new_payment_entry)

        update_fields = {
            "billed_amount": new_total_paid,
            "due_update_date": timezone.now(),
            "payments": current_payments
        }
        if new_total_paid >= net_amount:
            update_fields["billing_status"] = "Billed"
            
        Billing.objects.filter(pk=billing.pk).update(**update_fields)

        # Direct PyMongo ensure native BSON array storage in MongoDB
        try:
            mongo_url = os.getenv("GLOBAL_DB_HOST")
            if mongo_url:
                client = MongoClient(mongo_url)
                db = client["franchise"]
                coll = db["franchise_billing"]
                coll.update_one(
                    {"barcode": barcode},
                    {"$set": {"payments": current_payments}}
                )
        except Exception as mongo_err:
            print("Direct MongoDB payments array update warning:", mongo_err)

        # Create payment transaction record
        PaymentTransaction.objects.create(
            franchise_id=billing.franchise_id,
            barcode=barcode,
            amount_paid=payment_amount,
            payment_mode=payment_mode,
            remarks=remarks,
        )

        return Response(
            {
                "message": "Due amount updated successfully",
                "new_due": str(new_due),
                "total_paid": str(new_total_paid),
                "net_amount": str(net_amount),
                "due_update_date": timezone.now().isoformat(),
                "payments": current_payments
            },
            status=200,
        )

    except Billing.DoesNotExist:
        return Response({"error": "Billing record not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


def calculate_tally_for_date(franchise_id, target_date):
    """
    Helper function to calculate cash tally metrics for a specific date.
    Returns a dictionary with Decimal values.
    """
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    
    # 1. Calculate Total Billing & Shares (from FranchiseMonthlyRevenue)
    revenue_collection = db["franchise_franchisemonthlyrevenue"]
    monthly_id = f"{franchise_id}-{target_date.year}{target_date.month:02d}"
    revenue_doc = revenue_collection.find_one({"monthly_id": monthly_id})
    
    total_billing_today = Decimal('0.00')
    
    if revenue_doc:
        refs = revenue_doc.get("registrations_refs", [])
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except:
                refs = []
        
        for ref in refs:
            try:
                b_date = datetime.fromisoformat(ref.get('billed_date', '')).date()
                if b_date == target_date:
                    total_billing_today += Decimal(str(ref.get('amount', 0)))
            except:
                pass
                
    franchise_share = total_billing_today / Decimal('2.00')
    franchiser_share = total_billing_today / Decimal('2.00')

    # 2. Calculate Collections (from Billing)
    billing_collection = db["franchise_billing"]
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())

    # A. Collected from New Registrations
    new_bills = billing_collection.find({
        "franchise_id": franchise_id,
        "registrationDate": {"$gte": start_of_day, "$lte": end_of_day}
    })
    
    collected_from_new = Decimal('0.00')
    for bill in new_bills:
        amt = bill.get('billed_amount', 0)
        if isinstance(amt, Decimal128):
            amt = amt.to_decimal()
        collected_from_new += Decimal(str(amt))

    # B. Collected from Past Dues
    past_bills = billing_collection.find({
        "franchise_id": franchise_id,
        "registrationDate": {"$lt": start_of_day},
        "due_update_date": {"$gte": start_of_day, "$lte": end_of_day}
    })
    
    collected_from_past_dues = Decimal('0.00')
    
    for bill in past_bills:
        payments = bill.get('payments', [])
        if isinstance(payments, str):
            try:
                payments = json.loads(payments)
            except:
                payments = []
        
        if isinstance(payments, list):
            for p in payments:
                try:
                    p_date_str = p.get('date', '')
                    if p_date_str:
                        p_date = datetime.fromisoformat(p_date_str).date()
                        if p_date == target_date:
                            collected_from_past_dues += Decimal(str(p.get('amount', 0)))
                except:
                    pass

    total_collection_today = collected_from_new + collected_from_past_dues
    
    client.close()

    return {
        "total_billing_amount": total_billing_today,
        "franchise_share": franchise_share,
        "franchiser_share": franchiser_share,
        "collected_from_new_registrations": collected_from_new,
        "collected_from_past_dues": collected_from_past_dues,
        "total_collection_today": total_collection_today
    }


@api_view(['GET'])
def get_cash_tally(request):
    franchise_id = request.GET.get('franchise_id')
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')
    
    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)
        
    try:
        # Determine Date Range
        if from_date_str and to_date_str:
            start_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        else:
            # Default to current month
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today

        daily_stats = []
        total_stats = {
            "total_billing_amount": Decimal('0.00'),
            "franchise_share": Decimal('0.00'),
            "franchiser_share": Decimal('0.00'),
            "collected_from_new_registrations": Decimal('0.00'),
            "collected_from_past_dues": Decimal('0.00'),
            "total_collection_today": Decimal('0.00')
        }

        current_date = start_date
        while current_date <= end_date:
            data = calculate_tally_for_date(franchise_id, current_date)
            
            # Append to daily list
            daily_stats.append({
                "date": current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
                "total_billing_amount": f"{data['total_billing_amount']:.2f}",
                "franchise_share": f"{data['franchise_share']:.2f}",
                "franchiser_share": f"{data['franchiser_share']:.2f}",
                "collected_from_new_registrations": f"{data['collected_from_new_registrations']:.2f}",
                "collected_from_past_dues": f"{data['collected_from_past_dues']:.2f}",
                "total_collection_today": f"{data['total_collection_today']:.2f}"
            })

            # Accumulate totals
            for key in total_stats:
                total_stats[key] += data[key]
            
            current_date += timedelta(days=1)

        # Convert totals to two-decimal string
        total_stats_str = {k: f"{v:.2f}" for k, v in total_stats.items()}

        return Response({
            "daily_stats": daily_stats,
            "total_stats": total_stats_str
        }, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def export_daily_tally(request):
    franchise_id = request.GET.get('franchise_id')
    date_str = request.GET.get('date')
    
    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)
        
    try:
        if date_str:
            target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            target_dt = datetime.now()
        target_date = target_dt.date()
        
        data = calculate_tally_for_date(franchise_id, target_date)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Daily_Tally_{target_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Billing Date', 'Gross Billed Amount', 'Franchise Share (50%)', 'Hospital Share (50%)', "Today's Registration Receipts", 'Past Due Recoveries', 'Total Cash Collected'])
        writer.writerow([
            target_date,
            data['total_billing_amount'],
            data['franchise_share'],
            data['franchiser_share'],
            data['collected_from_new_registrations'],
            data['collected_from_past_dues'],
            data['total_collection_today']
        ])
        
        return response

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def export_monthly_tally(request):
    franchise_id = request.GET.get('franchise_id')
    date_str = request.GET.get('date') # Any date within the desired month
    
    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)
        
    try:
        if date_str:
            target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            target_dt = datetime.now()
            
        year = target_dt.year
        month = target_dt.month
        
        num_days = calendar.monthrange(year, month)[1]
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Monthly_Tally_{year}_{month:02d}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Billing Date', 'Gross Billed Amount', 'Franchise Share (50%)', 'Hospital Share (50%)', "Today's Registration Receipts", 'Past Due Recoveries', 'Total Cash Collected'])
        
        # Initialize totals
        totals = {
            "total_billing_amount": Decimal('0.00'),
            "franchise_share": Decimal('0.00'),
            "franchiser_share": Decimal('0.00'),
            "collected_from_new_registrations": Decimal('0.00'),
            "collected_from_past_dues": Decimal('0.00'),
            "total_collection_today": Decimal('0.00')
        }
        
        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            data = calculate_tally_for_date(franchise_id, current_date)
            
            writer.writerow([
                current_date,
                data['total_billing_amount'],
                data['franchise_share'],
                data['franchiser_share'],
                data['collected_from_new_registrations'],
                data['collected_from_past_dues'],
                data['total_collection_today']
            ])
            
            # Accumulate totals
            for key in totals:
                totals[key] += data[key]
                
        # Write Total Row
        writer.writerow([])
        writer.writerow([
            'TOTAL',
            totals['total_billing_amount'],
            totals['franchise_share'],
            totals['franchiser_share'],
            totals['collected_from_new_registrations'],
            totals['collected_from_past_dues'],
            totals['total_collection_today']
        ])
        
        return response

    except Exception as e:
        return Response({"error": str(e)}, status=500)