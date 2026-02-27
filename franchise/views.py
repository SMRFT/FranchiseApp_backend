# views.py
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework import status
from django.http import HttpResponse
from bson.json_util import dumps
from pymongo import MongoClient
import os
from datetime import datetime, date
from django.utils import timezone
import json
import re
from datetime import datetime, timedelta
from .models import Patient
from .serializers import PatientSerializer, RefBySerializer
import gridfs
from bson import ObjectId
from .models import Patient, Billing,FranchiseMonthlyRevenue, RevenueShareModel,RefBy
from .serializers import BillingSerializer
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.dateparse import parse_date
from django.forms.models import model_to_dict
from django.db.models import Q
from dotenv import load_dotenv
from django.contrib.auth.hashers import check_password
from collections import Counter
from django.utils import timezone
from django.db import models  # ✅ required import

load_dotenv()

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.forms.models import model_to_dict
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from datetime import datetime
import traceback
import re
import json
import os
import gridfs
from pymongo import MongoClient
from rest_framework.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal, InvalidOperation
from bson.decimal128 import Decimal128

def validate_decimal_field(value, field_name, max_digits=12, decimal_places=2):
    """
    Validate decimal field with proper constraints
    """
    try:
        decimal_value = clean_decimal(value)
        
        # Check for negative values
        if decimal_value < 0:
            return False, f"{field_name} cannot be negative"
        
        # Check decimal places
        if decimal_value.as_tuple().exponent < -decimal_places:
            return False, f"{field_name} cannot have more than {decimal_places} decimal places"
        
        # Check total digits
        total_digits = len(str(decimal_value).replace('.', '').replace('-', ''))
        if total_digits > max_digits:
            return False, f"{field_name} is too large (max {max_digits} digits)"
        
        return True, decimal_value
        
    except Exception as e:
        return False, f"Invalid {field_name}: {str(e)}"



import re
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
import gridfs, os, json, traceback

from .Payment.payment_models import Wallet

def check_wallet_balance(franchise_id):
    try:
        wallet = Wallet.objects.get(franchise_id=franchise_id)
        wallet_balance = wallet.balance
    except Wallet.DoesNotExist:
        return False, "Wallet not found"

    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    collection = db["franchise_franchisemonthlyrevenue"]

    current_date = timezone.now()
    year = current_date.year
    month = current_date.month
    monthly_id = f"{franchise_id}-{year}{month:02d}"

    revenue_doc = collection.find_one({"monthly_id": monthly_id})
    franchise_share = Decimal("0.00")
    
    if revenue_doc:
        franchise_share = Decimal(str(revenue_doc.get("franchise_share", "0.00")))

    # Ensure wallet_balance is Decimal
    wallet_balance = Decimal(str(wallet_balance))

    if (wallet_balance - franchise_share) < 1000:
        return False, "Insufficient wallet balance (below 1000)"
    
    return True, "Sufficient balance"

@api_view(['GET'])
def get_wallet_balance(request):
    franchise_id = request.GET.get("franchise_id")
    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)
    
    try:
        wallet = Wallet.objects.get(franchise_id=franchise_id)
        wallet_balance = wallet.balance
    except Wallet.DoesNotExist:
        return Response({"error": "Wallet not found"}, status=404)

    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    collection = db["franchise_franchisemonthlyrevenue"]

    current_date = timezone.now()
    year = current_date.year
    month = current_date.month
    monthly_id = f"{franchise_id}-{year}{month:02d}"

    revenue_doc = collection.find_one({"monthly_id": monthly_id})
    franchise_share = Decimal("0.00")
    
    if revenue_doc:
        franchise_share = Decimal(str(revenue_doc.get("franchise_share", "0.00")))
    
    # Ensure wallet_balance is Decimal
    wallet_balance = Decimal(str(wallet_balance))
    
    available_balance = wallet_balance - franchise_share

    return Response({
        "wallet_balance": float(wallet_balance),
        "current_month_share": float(franchise_share),
        "available_balance": float(available_balance)
    }, status=200)

@csrf_exempt
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def register_patient(request):
    """Register patient with pending billing status"""
    data = request.data.copy()
    
    franchise_id = data.get("franchise_id")
    if franchise_id:
        is_allowed, msg = check_wallet_balance(franchise_id)
        if not is_allowed:
            return Response({"error": msg}, status=400)

    trf_file = request.FILES.get("trf")
    barcode_id = data.get("barcodeId")

    def generate_unique_patient_id():
        last_patient = (
            Patient.objects.exclude(patient_id=None)
            .order_by("-patient_id")  # ✅ use patient_id instead of id
            .first()
        )

        if last_patient and last_patient.patient_id:
            match = re.search(r"SDF(\d+)", last_patient.patient_id)
            last_number = int(match.group(1)) if match else 0
        else:
            last_number = 0
        new_number = last_number + 1
        return f"SDF{new_number:03d}"  # always 3 digits padded

    try:
        with transaction.atomic():
            existing_patient = None
            patient_id = data.get("patient_id")
            phone = data.get("phoneNumber")

            if patient_id:
                existing_patient = Patient.objects.filter(patient_id=patient_id).first()
            elif phone:
                existing_patient = Patient.objects.filter(phoneNumber=phone).first()

            if existing_patient:
                patient = existing_patient
                patient.franchise_id = data.get("franchise_id")
                patient.save()
            else:
                # Generate patient ID only for new patients
                unique_patient_id = generate_unique_patient_id()
                patient_data = {
                    "patient_id": unique_patient_id,
                    "patientname": data.get("patientname"),
                    "age": data.get("age"),
                    "gender": data.get("gender"),
                    "phoneNumber": phone,
                    "email": data.get("email"),
                    "city": data.get("city"),
                    "area": data.get("area"),
                    "pincode": data.get("pincode"),
                    "dateOfBirth": data.get("dateOfBirth"),
                    "franchise_id": data.get("franchise_id"),
                }
                patient_serializer = PatientSerializer(data=patient_data)
                if not patient_serializer.is_valid():
                    return Response(
                        {"error": "Invalid patient data", "details": patient_serializer.errors},
                        status=400,
                    )
                patient = patient_serializer.save()

            # Handle TRF file upload
            trf_file_id = None
            if trf_file:
                mongo_url = os.getenv("MONGO_URL")
                client = MongoClient(mongo_url)
                db = client["franchise"]
                fs = gridfs.GridFS(db)
                file_id = fs.put(
                    trf_file,
                    filename=trf_file.name,
                    content_type=trf_file.content_type,
                )
                trf_file_id = str(file_id)

            # Parse registration date
            if "registrationDate" in data:
                try:
                    data["registrationDate"] = datetime.strptime(
                        data["registrationDate"], "%Y-%m-%dT%H:%M"
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid registrationDate format. Use YYYY-MM-DDTHH:MM"},
                        status=400,
                    )
            
            payments = data.get("payments")
            if payments:
                try:
                    payments = json.loads(payments)
                except:
                    pass
            
            address = data.get("address")

            # Validate and clean decimal fields
            total_amount = clean_decimal(data.get("total", 0))
            net_amount = clean_decimal(data.get("netAmount", 0))

            is_valid_total, total_result = validate_decimal_field(total_amount, "total", 12, 2)
            if not is_valid_total:
                return Response({"error": total_result}, status=400)
            total_amount = total_result

            is_valid_net, net_result = validate_decimal_field(net_amount, "netAmount", 12, 2)
            if not is_valid_net:
                return Response({"error": net_result}, status=400)
            net_amount = net_result

            register_data = {
                "patient": patient.pk,
                "registrationDate": data.get("registrationDate"),
                "registeredBy": data.get("registeredBy"),
                "referredDoctor": data.get("referredDoctor"),
                "trf_file_id": trf_file_id,
                "testdetails": json.loads(data.get("testdetails"))
                if data.get("testdetails")
                else None,
                "total": total_amount,
                "discountPercentage": data.get("discountPercentage"),
                "discountAmount": data.get("discountAmount"),
                "netAmount": net_amount,
                "paymentMode": data.get("paymentMode"),
                "payments": payments,
                "address": address,
                "billing_status": "Pending",
                "billed_amount": Decimal("0.00"),
                "segment": data.get("segment"),
                "barcode": barcode_id,
                "franchise_id": data.get("franchise_id"),
            }

            serializer = BillingSerializer(data=register_data)
            if serializer.is_valid():
                registration = serializer.save()
                return Response(
                    {
                        "message": "Patient registration completed successfully",
                        "patient_id": patient.patient_id,
                        "barcode": barcode_id,
                        "billing_status": "Pending",
                        "net_amount": float(net_amount),
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print("Error in registration:", e)
        print(traceback.format_exc())
        return Response(
            {"error": f"Registration failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


from decimal import Decimal, InvalidOperation

def clean_decimal(value):
    """Ensure a value is always a Decimal."""
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')


from decimal import Decimal
import traceback
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.utils import timezone
from pymongo import MongoClient
from decimal import Decimal
import os, traceback
import datetime

@api_view(['PATCH'])
def confirm_billing(request):
    barcode = request.data.get("barcode")
    billed_amount = request.data.get("billed_amount")

    if not barcode:
        return Response({"error": "Barcode is required"}, status=400)
    if not billed_amount:
        return Response({"error": "Billed amount is required"}, status=400)

    # ✅ Validate decimal input
    is_valid_billed, billed_result = validate_decimal_field(
        billed_amount, "billed_amount", 12, 2
    )
    if not is_valid_billed:
        return Response({"error": billed_result}, status=400)

    billed_amount_decimal = clean_decimal(billed_result)

    try:
        with transaction.atomic():
            registration = Billing.objects.select_for_update().get(barcode=barcode)

            if registration.billing_status == "Billed":
                return Response({"error": "Already billed"}, status=400)

            # ✅ Update Register
            registration.billed_amount = billed_amount_decimal
            registration.billing_status = "Billed"
            registration.save(update_fields=["billed_amount", "billing_status"])

            # ✅ Update MongoDB monthly revenue
            mongo_url = os.getenv("GLOBAL_DB_HOST")
            client = MongoClient(mongo_url)
            db = client["franchise"]
            franchiserevenue_collection = db["franchise_franchisemonthlyrevenue"]

            current_date = timezone.now()
            year, month = current_date.year, current_date.month
            franchise_id = registration.franchise_id

            if franchise_id:
                monthly_id = f"{franchise_id}-{year}{month:02d}"

                # Find or create monthly revenue doc
                revenue_doc = franchiserevenue_collection.find_one({
                    "monthly_id": monthly_id
                })

                billed_entry = {
                    "barcode": barcode,
                    "amount": float(billed_amount_decimal),
                    "billed_date": current_date.isoformat()
                }

                if revenue_doc:
                    # ✅ Update existing
                    refs = revenue_doc.get("registrations_refs", [])
                    # Ensure it's a list
                    if isinstance(refs, str):
                        import json
                        try:
                            refs = json.loads(refs)
                        except:
                            refs = []

                    # Replace if barcode already exists
                    updated = False
                    for r in refs:
                        if r.get("barcode") == barcode:
                            r.update(billed_entry)
                            updated = True
                            break
                    if not updated:
                        refs.append(billed_entry)

                    # Recompute totals
                    total_revenue = sum(Decimal(str(r["amount"])) for r in refs)
                    franchise_share = total_revenue / 2
                    franchiser_share = total_revenue / 2

                    franchiserevenue_collection.update_one(
                        {"monthly_id": monthly_id},
                        {
                            "$set": {
                                "total_revenue": str(total_revenue),
                                "franchise_share": str(franchise_share),
                                "franchiser_share": str(franchiser_share),
                                "registrations_refs": refs,
                                "lastmodified_date": current_date,
                                "lastmodified_by": "system"
                            }
                        }
                    )

                else:
                    # ✅ Create new monthly doc
                    total_revenue = billed_amount_decimal
                    franchise_share = total_revenue / 2
                    franchiser_share = total_revenue / 2

                    franchiserevenue_collection.insert_one({
                        "monthly_id": monthly_id,
                        "franchise_id": franchise_id,
                        "year": year,
                        "month": month,
                        "total_revenue": str(total_revenue),
                        "franchise_share": str(franchise_share),
                        "franchiser_share": str(franchiser_share),
                        "revenue_share_model_id": None,
                        "wallet_amount_reduced": str(Decimal("0.00")),
                        "registrations_refs": [billed_entry],
                        "status": "active",
                        "created_date": current_date,
                        "created_by": "system",
                        "lastmodified_date": current_date,
                        "lastmodified_by": "system"
                    })

            return Response({
                "message": "Billing confirmed successfully",
                "barcode": barcode,
                "billed_amount": float(billed_amount_decimal),
                "billing_status": "Billed",
                "franchise_share": float(franchise_share) if franchise_id else None,
                "franchiser_share": float(franchiser_share) if franchise_id else None,
                "monthly_total": float(total_revenue) if franchise_id else None,
                "revenue_model": "50/50 Fixed" if franchise_id else None
            }, status=200)

    except Billing.DoesNotExist:
        return Response({"error": "Registration not found"}, status=404)
    except Exception as e:
        print(traceback.format_exc())
        return Response({"error": str(e)}, status=500)






@api_view(['GET'])
def search_patient(request):
    query = request.GET.get("query", "")

    if not query:
        return Response({"error": "Missing query parameter"}, status=400)

    try:
        patient = Patient.objects.filter(
            Q(patient_id=query) | Q(phoneNumber=query)
        ).order_by("-created_date").first()

        if patient:
            serializer = PatientSerializer(patient)
            return Response({"patient": serializer.data}, status=200)
        else:
            return Response({"patient": None}, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)



mongo_url = os.getenv("GLOBAL_DB_HOST")
client = MongoClient(mongo_url)
db = client["franchise"]
user_collection = db["franchise_user"]

@api_view(["POST"])
def login_view(request):
    franchise_id = request.data.get("franchise_id")
    password = request.data.get("password")
    if not franchise_id or not password:
        return Response({"message": "franchise_id and password required"}, status=status.HTTP_400_BAD_REQUEST)
    user = user_collection.find_one({"franchise_id": franchise_id})
    franchise_collection = db["franchise_franchise"]
    if not user:
        return Response({"message": "Invalid franchise ID"}, status=status.HTTP_404_NOT_FOUND)
    # :white_check_mark: Check is_active from franchise_collection
    franchise_data = franchise_collection.find_one({"franchise_id": franchise_id})
    print("this",franchise_data)
    if not franchise_data:
        return Response({"message": "Franchise data not found"}, status=status.HTTP_404_NOT_FOUND)
    if not franchise_data.get("is_active", False):
        return Response({"message": "Franchise is inactive. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
    stored_password = user.get("password")
    if check_password(password, stored_password):
        # :white_check_mark: Extract franchiser name if available
        franchise_name = franchise_data.get("franchise_name", "Unknown Franchise")
        return Response({
            "message": "Login successful",
            "franchise_id": franchise_id,
            "email": user.get("email"),
            "name": franchise_name,
        })
    else:
        return Response({"message": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

    

@api_view(['GET'])
def get_all_patients(request):
    franchise_id = request.GET.get('franchise_id')
    if franchise_id:
        patients = Patient.objects.filter(franchise_id=franchise_id).order_by('-created_date')
    else:
        patients = Patient.objects.all().order_by('-created_date')

    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime, timedelta
from .models import Billing, Patient
from .serializers import BillingSerializer, PatientSerializer
from bson.objectid import ObjectId  # If needed
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime, time
from django.db.models import Q
@api_view(["GET"])
def get_registrations_by_franchise_and_date(request):
    """
    Get registrations by franchise with date range filtering.
    
    Query Parameters:
    - franchise_id (required): Franchise ID
    - start_date (optional): Start date in YYYY-MM-DD format
    - end_date (optional): End date in YYYY-MM-DD format
    - date (optional): Single date for backward compatibility
    
    Examples:
    - /api/registrations/?franchise_id=SHF004&start_date=2025-11-01&end_date=2025-11-17
    - /api/registrations/?franchise_id=SHF004&date=2025-11-17  (backward compatible)
    """
    franchise_id = request.GET.get("franchise_id")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    date_str = request.GET.get("date")  # For backward compatibility

    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)

    # Handle date filtering
    try:
        if start_date_str and end_date_str:
            # Date range filtering
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            
            # Validate date range
            if start_date > end_date:
                return Response({"error": "start_date cannot be after end_date"}, status=400)
            
            # Create datetime range for the entire day range
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
            
        elif date_str:
            # Single date filtering (backward compatibility)
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_datetime = datetime.combine(date, time.min)
            end_datetime = datetime.combine(date, time.max)
            
        else:
            return Response({
                "error": "Either (start_date and end_date) or date is required"
            }, status=400)
            
    except ValueError as e:
        return Response({
            "error": f"Invalid date format. Use YYYY-MM-DD. Details: {str(e)}"
        }, status=400)

    # Filter registrations for that franchise within the date range
    registrations = Billing.objects.filter(
        franchise_id=franchise_id,
        registrationDate__gte=start_datetime,
        registrationDate__lte=end_datetime
    ).order_by("-registrationDate")

    # Check if no results found
    if not registrations.exists():
        return Response([], status=200)

    # Build response with patient info
    results = []
    for reg in registrations:
        try:
            # Fetch related patient data using patient_id
            patient = Patient.objects.get(patient_id=reg.patient_id)
            patient_data = {
                "patientname": patient.patientname,
                "phoneNumber": patient.phoneNumber,
                "email": patient.email,
                "city": patient.city,
                "area": patient.area,
            }
        except Patient.DoesNotExist:
            # Handle missing patient data gracefully
            patient_data = {
                "patientname": "N/A",
                "phoneNumber": "N/A",
                "email": "N/A",
                "city": "N/A",
                "area": "N/A",
            }

        # Serialize registration data
        reg_data = BillingSerializer(reg).data
        reg_data["patient_info"] = patient_data
        
        # Add created_date for consistency
        reg_data["created_date"] = reg.registrationDate.isoformat()
        
        results.append(reg_data)

    return Response(results, status=200)




@api_view(['PUT'])
def update_patient(request, pk):
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({"message": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    # Copy request data, but don't include patient_id
    update_data = request.data.copy()
    update_data['patient_id'] = patient.patient_id  # Ensure patient_id stays the same

    # Pass data to serializer WITHOUT lastmodified_date
    serializer = PatientSerializer(patient, data=update_data)
    if serializer.is_valid():
        updated_instance = serializer.save()

        # ✅ Update lastmodified_date manually and save again
        updated_instance.lastmodified_date = datetime.now()
        updated_instance.save()

        return Response({"message": "Patient updated", "data": PatientSerializer(updated_instance).data}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_patient_by_id(request, patient_id):
    try:
        patient = Patient.objects.get(patient_id=patient_id)
        serializer = PatientSerializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Patient.DoesNotExist:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def patient_list_by_date(request):
    date_str = request.GET.get('date')  # Expecting 'YYYY-MM-DD'

    if date_str:
        try:
            # Parse the start of the day
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            # Get the end of that day (exclusive)
            end_date = start_date + timedelta(days=1)

            patients = Patient.objects.filter(
                created_date__gte=start_date,
                created_date__lt=end_date
            )
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)
    else:
        patients = Patient.objects.all()

    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_test_details(request):
    try:
        # MongoDB connection
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["Diagnostics"]
        collection = db["core_testdetails"]

        # Fetch only active test details
        test_details = list(collection.find({"is_active": True}))

        # Convert ObjectId to string for JSON serialization
        for test in test_details:
            test["_id"] = str(test["_id"])

        return Response(test_details, status=200)
    
    except Exception as e:
        return Response({"error": str(e)}, status=500)



@api_view(['GET'])
def get_active_franchise_locations(request):
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_location_details"]

        # Only fetch documents where is_active is true
        data = list(collection.find({ "is_active": True }))

        json_data = dumps(data, indent=2)  # Converts ObjectId and datetime properly

        return HttpResponse(json_data, content_type="application/json")

    except Exception as e:
        return HttpResponse(dumps({ "error": str(e) }), content_type="application/json", status=500)
    

@api_view(['PATCH'])
def update_barcode_status(request, barcode_id):
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_barcoderange"]

        # Parse request body
        new_status = request.data.get("is_active")
        if new_status is None:
            return Response({"error": "Missing 'is_active' field"}, status=400)

        # Update the is_active field
        result = collection.update_one(
            {"_id": ObjectId(barcode_id)},
            {"$set": {"is_active": new_status}}
        )

        if result.matched_count == 0:
            return Response({"error": "Document not found"}, status=404)

        return Response({"message": "Status updated successfully"})

    except Exception as e:
        return Response({"error": str(e)}, status=500)


from .models import Billing, Sample # Assuming these are Django models or Mongoengine documents
# Helper to parse date string
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()




from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from django.conf import settings
from .models import Billing
import os

@api_view(['GET'])
def check_barcode_exists(request):
    barcode_id = request.GET.get("barcodeId")

    if not barcode_id:
        return Response({"error": "barcodeId is required."}, status=400)

    # 1. Check if barcode already registered in Register model
    if Billing.objects.filter(barcode=barcode_id).exists():
        return Response({"exists": True, "valid": False, "message": "This barcode is already used."}, status=200)

    # 2. Connect to MongoDB
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]

    # 3. Check if barcode is already registered in franchise_register collection
    franchise_register = db["franchise_register"]
    if franchise_register.find_one({"barcode": barcode_id}):
        return Response({"exists": True, "valid": False, "message": "This barcode is already registered in franchise_register."}, status=200)

    # 4. Check all franchise_barcodestock ranges
    barcode_stock = db["franchise_barcodestock"]
    try:
        barcode_int = int(barcode_id)
    except ValueError:
        return Response({"exists": False, "valid": False, "message": "Invalid barcode format (should be numeric)."}, status=200)

    matching_range = barcode_stock.find_one({
        "$expr": {
            "$and": [
                {"$lte": [{"$toInt": "$startbarcode"}, barcode_int]},
                {"$gte": [{"$toInt": "$endbarcode"}, barcode_int]}
            ]
        }
    })

    if matching_range:
        return Response({"exists": False, "valid": True, "message": "Barcode is valid and within allowed range."}, status=200)
    else:
        return Response({"exists": False, "valid": False, "message": "Barcode is not in any registered stock range."}, status=200)


from .models import Billing, Sample # Assuming these are Django models or Mongoengine documents
# Helper to parse date string
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()

@csrf_exempt
@api_view(['GET'])
def get_patient_by_franchise_and_date(request):

    franchise_id = request.GET.get('franchise_id')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    date_str = request.GET.get('date')

    if not franchise_id:
        return JsonResponse({'error': 'Missing franchise_id'}, status=400)

    try:
        # ─────────────────────────────
        # Date Handling
        # ─────────────────────────────
        if start_date_str and end_date_str:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)

            if not start_date or not end_date:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

            if start_date > end_date:
                return JsonResponse({'error': 'start_date cannot be after end_date'}, status=400)

            date_from = start_date
            date_to = end_date + timedelta(days=1)

        elif date_str:
            target_date = parse_date(date_str)
            if not target_date:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

            date_from = target_date
            date_to = target_date + timedelta(days=1)
        else:
            return JsonResponse({
                'error': 'Either (start_date and end_date) or date is required'
            }, status=400)

        registrations = Billing.objects.filter(
            franchise_id=franchise_id,
            registrationDate__gte=date_from,
            registrationDate__lt=date_to
        ).select_related('patient').order_by('-registrationDate')

        if not registrations.exists():
            return JsonResponse([], safe=False)

        # ─────────────────────────────
        # MongoDB Connections
        # ─────────────────────────────
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)

        franchise_db = client["franchise"]
        sample_collection = franchise_db["franchise_sample"]

        diagnostics_db = client["Diagnostics"]
        testdetails_collection = diagnostics_db["core_testdetails"]

        result = []
        all_test_ids = set()

        # First collect test_ids
        for reg in registrations:
            testdetails = reg.testdetails
            if isinstance(testdetails, str):
                try:
                    testdetails = json.loads(testdetails)
                except:
                    testdetails = []

            for test in testdetails:
                if isinstance(test, dict) and test.get("test_id"):
                    all_test_ids.add(test.get("test_id"))

        # Batch fetch specimen data
        test_docs = list(testdetails_collection.find(
            {"test_id": {"$in": list(all_test_ids)}},
            {"test_id": 1, "specimen_type": 1, "collection_container": 1, "_id": 0}
        ))

        test_map = {
            doc["test_id"]: {
                "specimen_type": doc.get("specimen_type"),
                "collection_container": doc.get("collection_container")
            }
            for doc in test_docs
        }

        # Process registrations
        for reg in registrations:
            barcode = reg.barcode

            sample_doc = sample_collection.find_one({
                "franchise_id": franchise_id,
                "barcode": barcode
            })

            should_display_patient = False

            if sample_doc is None:
                should_display_patient = True
            else:
                sample_testdetails = sample_doc.get("testdetails", [])
                if isinstance(sample_testdetails, str):
                    try:
                        sample_testdetails = json.loads(sample_testdetails)
                    except:
                        sample_testdetails = []

                if any(test.get('samplestatus') == 'Pending'
                       for test in sample_testdetails if isinstance(test, dict)):
                    should_display_patient = True

            if should_display_patient:

                # Enrich testdetails
                enriched_tests = []
                reg_tests = reg.testdetails
                if isinstance(reg_tests, str):
                    try:
                        reg_tests = json.loads(reg_tests)
                    except:
                        reg_tests = []

                for test in reg_tests:
                    if isinstance(test, dict):
                        test_id = test.get("test_id")
                        extra = test_map.get(test_id, {})
                        test["specimen_type"] = extra.get("specimen_type", "N/A")
                        test["collection_container"] = extra.get("collection_container", "N/A")
                        enriched_tests.append(test)

                result.append({
                    'barcode': barcode,
                    'patient_id': reg.patient.patient_id if reg.patient else None,
                    'patientname': reg.patient.patientname if reg.patient else None,
                    'franchise_id': reg.franchise_id,
                    'registrationDate': reg.registrationDate.isoformat() if reg.registrationDate else None,
                    'testdetails': enriched_tests,
                })

        client.close()
        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET', 'POST', 'PATCH'])
def sample(request):
    """
    Sample API with support for date range filtering.
    
    GET Parameters:
    - barcode + franchise_id: Get specific sample
    - franchise_id + start_date + end_date: Get samples in date range
    - franchise_id + date: Single date (backward compatible)
    """
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    sample_collection = db["franchise_sample"]
    register_collection = db["franchise_billing"]

    if request.method == 'POST':
        franchise_id = request.data.get('franchise_id')
        barcode = request.data.get('barcode')
        incoming_testdetails = request.data.get('testdetails', [])

        if not isinstance(incoming_testdetails, list):
            return Response({"error": "testdetails must be a list of objects"}, status=status.HTTP_400_BAD_REQUEST)

        # Check for existing sample using both franchise_id and barcode
        existing_sample = sample_collection.find_one({
            "franchise_id": franchise_id,
            "barcode": barcode
        })

        if existing_sample:
            # Update existing sample document
            existing_testdetails_str = existing_sample.get('testdetails', '[]')
            existing_testdetails = []
            if isinstance(existing_testdetails_str, str):
                try:
                    existing_testdetails = json.loads(existing_testdetails_str)
                except json.JSONDecodeError:
                    existing_testdetails = []
            elif isinstance(existing_testdetails_str, list):
                existing_testdetails = existing_testdetails_str

            # Use test_id as the unique key
            incoming_updates_map = {}
            for test_item in incoming_testdetails:
                if isinstance(test_item, dict):
                    test_id = test_item.get('test_id')
                    if test_id:
                        incoming_updates_map[test_id] = test_item

            final_testdetails_list = []
            # Update existing tests based on test_id
            for existing_test in existing_testdetails:
                if isinstance(existing_test, dict):
                    test_id = existing_test.get('test_id')
                    if test_id and test_id in incoming_updates_map:
                        updated_test_data = incoming_updates_map[test_id]
                        existing_test['samplestatus'] = updated_test_data.get('samplestatus', existing_test.get('samplestatus'))
                        existing_test['samplecollected_time'] = updated_test_data.get('samplecollected_time', existing_test.get('samplecollected_time'))

                        # Set collected_by on existing_test
                        if updated_test_data.get('samplestatus') == 'Collected' and franchise_id:
                            existing_test['collected_by'] = franchise_id

                        final_testdetails_list.append(existing_test)
                        del incoming_updates_map[test_id]
                    else:
                        final_testdetails_list.append(existing_test)
            
            # Add any new tests that were not in existing_testdetails
            for test_id, new_test_data in incoming_updates_map.items():
                if new_test_data.get('samplestatus') == 'Collected':
                    new_test_data['collected_by'] = franchise_id
                else:
                    new_test_data['collected_by'] = None
                final_testdetails_list.append(new_test_data)

            final_testdetails_json_str = json.dumps(final_testdetails_list)

            update_fields = {
                "testdetails": final_testdetails_json_str,
                "lastmodified_by": franchise_id,
                "lastmodified_date": datetime.now()
            }
            
            result = sample_collection.update_one(
                {"_id": existing_sample["_id"]},
                {"$set": update_fields}
            )
            if result.modified_count == 1:
                return Response({"message": "Sample updated successfully."}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No changes detected, sample not modified."}, status=status.HTTP_200_OK)
        
        else:
            # Create new sample document
            new_sample_doc = {
                "franchise_id": franchise_id,
                "barcode": barcode,
                "testdetails": [],
                "created_date": datetime.now(),
                "lastmodified_by": franchise_id,
                "lastmodified_date": datetime.now()
            }
            
            # Populate testdetails for the new document
            for test_item in incoming_testdetails:
                if isinstance(test_item, dict):
                    if test_item.get('samplestatus') == 'Collected':
                        test_item['collected_by'] = franchise_id
                    else:
                        test_item['collected_by'] = None
                    new_sample_doc['testdetails'].append(test_item)
            
            new_sample_doc['testdetails'] = json.dumps(new_sample_doc['testdetails'])

            insert_result = sample_collection.insert_one(new_sample_doc)
            if insert_result.inserted_id:
                return Response({"message": "Sample created successfully.", "id": str(insert_result.inserted_id)}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": "Failed to create sample."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'GET':
        barcode = request.GET.get('barcode')
        franchise_id = request.GET.get('franchise_id')
        date_str = request.GET.get('date')  # Single date (backward compatible)
        start_date_str = request.GET.get('start_date')  # Start date for range
        end_date_str = request.GET.get('end_date')  # End date for range

        if barcode and franchise_id:
            # Get specific sample by barcode and franchise_id
            sample_doc = sample_collection.find_one({
                "franchise_id": franchise_id,
                "barcode": barcode
            })

            if sample_doc:
                # Get patient_id from Register model using barcode
                register_doc = register_collection.find_one({"barcode": barcode})
                sample_doc['patient_id'] = register_doc.get('patient_id') if register_doc else None

                # Parse testdetails
                testdetails = sample_doc.get('testdetails', [])
                if isinstance(testdetails, str):
                    try:
                        testdetails = json.loads(testdetails)
                    except json.JSONDecodeError:
                        testdetails = []
                elif not isinstance(testdetails, list):
                    testdetails = [testdetails]

                sample_doc['testdetails'] = testdetails
                sample_doc['_id'] = str(sample_doc['_id'])

                return Response(sample_doc, status=200)
            else:
                return Response({"message": "No sample data found for this patient."}, status=404)

        elif franchise_id and (start_date_str and end_date_str or date_str):

            try:
                if start_date_str and end_date_str:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

                    if start_date > end_date:
                        return Response({"error": "start_date cannot be after end_date"}, status=400)

                    date_from = start_date
                    date_to = end_date + timedelta(days=1)

                elif date_str:
                    target_date = datetime.strptime(date_str, "%Y-%m-%d")
                    date_from = target_date
                    date_to = target_date + timedelta(days=1)

                # Diagnostics DB
                diagnostics_db = client["Diagnostics"]
                testdetails_collection = diagnostics_db["core_testdetails"]

                all_samples = sample_collection.find({
                    "franchise_id": franchise_id,
                    "created_date": {"$gte": date_from, "$lt": date_to}
                })

                result_samples = []
                all_test_ids = set()

                # Collect test_ids
                samples_list = list(all_samples)
                for sample_doc in samples_list:
                    testdetails_raw = sample_doc.get("testdetails", [])
                    if isinstance(testdetails_raw, str):
                        try:
                            testdetails = json.loads(testdetails_raw)
                        except:
                            testdetails = []
                    else:
                        testdetails = testdetails_raw

                    for test in testdetails:
                        if isinstance(test, dict) and test.get("test_id"):
                            all_test_ids.add(test.get("test_id"))

                # Batch fetch specimen info
                test_docs = list(testdetails_collection.find(
                    {"test_id": {"$in": list(all_test_ids)}},
                    {"test_id": 1, "specimen_type": 1, "collection_container": 1, "_id": 0}
                ))

                test_map = {
                    doc["test_id"]: {
                        "specimen_type": doc.get("specimen_type"),
                        "collection_container": doc.get("collection_container")
                    }
                    for doc in test_docs
                }

                # Enrich response
                for sample_doc in samples_list:

                    testdetails_raw = sample_doc.get("testdetails", [])
                    if isinstance(testdetails_raw, str):
                        try:
                            testdetails = json.loads(testdetails_raw)
                        except:
                            testdetails = []
                    else:
                        testdetails = testdetails_raw

                    collected_tests = []

                    for test in testdetails:
                        if isinstance(test, dict) and test.get("samplestatus") == "Collected":
                            test_id = test.get("test_id")
                            extra = test_map.get(test_id, {})

                            test["specimen_type"] = extra.get("specimen_type", "N/A")
                            test["collection_container"] = extra.get("collection_container", "N/A")

                            collected_tests.append(test)

                    if collected_tests:
                        sample_doc["_id"] = str(sample_doc["_id"])
                        sample_doc["testdetails"] = collected_tests

                        register_doc = register_collection.find_one({"barcode": sample_doc.get("barcode")})
                        sample_doc["patient_id"] = register_doc.get("patient_id") if register_doc else None

                        result_samples.append(sample_doc)

                return Response(result_samples, status=200)

            except Exception as e:
                return Response({'error': str(e)}, status=500)
        else:
            return Response({
                "error": "Missing required parameters. Provide either (barcode + franchise_id) or (franchise_id + start_date + end_date) or (franchise_id + date)"
            }, status=400)

    elif request.method == 'PATCH':
        franchise_id = request.data.get('franchise_id')
        barcode = request.data.get('barcode')
        incoming_testdetails = request.data.get('testdetails', [])

        if not franchise_id or not barcode or not isinstance(incoming_testdetails, list):
            return Response({"error": "franchise_id, barcode, and testdetails (list) are required for PATCH."}, status=400)

        existing_sample = sample_collection.find_one({
            "franchise_id": franchise_id,
            "barcode": barcode
        })

        if not existing_sample:
            return Response({"error": "Sample not found in MongoDB."}, status=404)

        # Parse existing testdetails from JSON string
        existing_testdetails_str = existing_sample.get('testdetails', '[]')
        existing_testdetails_list = []
        if isinstance(existing_testdetails_str, str):
            try:
                existing_testdetails_list = json.loads(existing_testdetails_str)
            except json.JSONDecodeError:
                existing_testdetails_list = []
        elif isinstance(existing_testdetails_str, list):
            existing_testdetails_list = existing_testdetails_str

        # Use test_id as the unique key for updates
        incoming_updates_map = {}
        for test_item in incoming_testdetails:
            if isinstance(test_item, dict):
                test_id = test_item.get('test_id')
                if test_id:
                    incoming_updates_map[test_id] = test_item

        # Update existing tests based on test_id
        updated_testdetails_list = []
        for existing_test in existing_testdetails_list:
            if isinstance(existing_test, dict):
                test_id = existing_test.get('test_id')
                if test_id and test_id in incoming_updates_map:
                    updated_test_data = incoming_updates_map[test_id]
                    new_status = updated_test_data.get('samplestatus', existing_test.get('samplestatus'))

                    existing_test['samplestatus'] = new_status

                    if new_status == 'Transferred':
                        existing_test['transferred_by'] = franchise_id
                        existing_test['sampletransferred_time'] = updated_test_data.get(
                            'sampletransferred_time',
                            datetime.now().isoformat()
                        )
                    else:
                        existing_test['transferred_by'] = existing_test.get('transferred_by')
                        existing_test['sampletransferred_time'] = existing_test.get('sampletransferred_time')

                    # Preserve collected_by and samplecollected_time if not already present
                    if 'collected_by' not in existing_test and 'collected_by' in updated_test_data:
                        existing_test['collected_by'] = updated_test_data['collected_by']
                    if 'samplecollected_time' not in existing_test and 'samplecollected_time' in updated_test_data:
                        existing_test['samplecollected_time'] = updated_test_data['samplecollected_time']

                    updated_testdetails_list.append(existing_test)
                    del incoming_updates_map[test_id]
                else:
                    updated_testdetails_list.append(existing_test)
            else:
                updated_testdetails_list.append(existing_test)

        # Add any new tests
        for test_id, new_test_data in incoming_updates_map.items():
            new_status = new_test_data.get('samplestatus')
            if new_status == 'Transferred':
                new_test_data['transferred_by'] = franchise_id
                new_test_data['sampletransferred_time'] = datetime.now().isoformat()
            else:
                new_test_data['transferred_by'] = new_test_data.get('transferred_by')
                new_test_data['sampletransferred_time'] = new_test_data.get('sampletransferred_time')
            updated_testdetails_list.append(new_test_data)

        final_testdetails_json_str = json.dumps(updated_testdetails_list)

        update_fields = {
            "testdetails": final_testdetails_json_str,
            "lastmodified_by": franchise_id,
            "lastmodified_date": datetime.now()
        }

        result = sample_collection.update_one(
            {"_id": existing_sample["_id"]},
            {"$set": update_fields}
        )
        
        client.close()  # Close MongoDB connection
        
        if result.modified_count == 1:
            return Response({"message": "Sample updated successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "No changes detected, sample not modified."}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_transferred_samples(request):
    franchise_id = request.GET.get('franchise_id')
    samplestatus = request.GET.get('samplestatus', 'Transferred')
    date_param = request.GET.get('date')
    start_date_param = request.GET.get('start_date')
    end_date_param = request.GET.get('end_date')

    if not franchise_id:
        return Response({'error': 'franchise_id is required'}, status=400)

    # ─────────────────────────────────────────────
    # MongoDB Connections
    # ─────────────────────────────────────────────
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)

        franchise_db = client["franchise"]
        billing_collection = franchise_db['franchise_billing']
        patient_collection = franchise_db['franchise_patient']

        # ✅ NEW: Diagnostics DB
        diagnostics_db = client["Diagnostics"]
        testdetails_collection = diagnostics_db["core_testdetails"]

    except Exception as e:
        return Response({'error': f'MongoDB connection failed: {str(e)}'}, status=500)

    # ─────────────────────────────────────────────
    # Fetch Django Sample records
    # ─────────────────────────────────────────────
    try:
        records = Sample.objects.filter(franchise_id=franchise_id)
    except Exception as e:
        client.close()
        return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────
    # Date Filtering
    # ─────────────────────────────────────────────
    if start_date_param and end_date_param:
        try:
            start_dt = datetime.strptime(start_date_param, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date_param, '%Y-%m-%d')

            if start_dt > end_dt:
                client.close()
                return Response({'error': 'start_date cannot be after end_date'}, status=400)

            start_aware = timezone.make_aware(datetime.combine(start_dt, datetime.min.time()))
            end_aware = timezone.make_aware(datetime.combine(end_dt, datetime.max.time()))

            records = records.filter(created_date__range=[start_aware, end_aware])

        except ValueError:
            client.close()
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    elif date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            start_aware = timezone.make_aware(datetime.combine(filter_date, datetime.min.time()))
            end_aware = timezone.make_aware(datetime.combine(filter_date, datetime.max.time()))

            records = records.filter(created_date__range=[start_aware, end_aware])

        except ValueError:
            client.close()
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    # ─────────────────────────────────────────────
    # Collect barcodes + test_ids
    # ─────────────────────────────────────────────
    barcode_tests_map = {}
    barcode_created_date = {}
    all_test_ids = set()

    for record in records:
        try:
            testdetails = record.testdetails

            if isinstance(testdetails, str):
                testdetails = json.loads(testdetails)

            if not isinstance(testdetails, list):
                testdetails = [testdetails]

            for test in testdetails:
                if (
                    isinstance(test, dict) and
                    test.get('samplestatus') == samplestatus and
                    test.get('batch_number') in [None, '', 'null']
                ):
                    barcode = record.barcode

                    if barcode not in barcode_tests_map:
                        barcode_tests_map[barcode] = []
                        barcode_created_date[barcode] = record.created_date

                    barcode_tests_map[barcode].append(test)

                    # ✅ Collect test_id
                    if test.get("test_id"):
                        all_test_ids.add(test.get("test_id"))

        except Exception:
            continue

    if not barcode_tests_map:
        client.close()
        return Response({'transferred_samples': []})

    # ─────────────────────────────────────────────
    # Fetch specimen_type & collection_container
    # ─────────────────────────────────────────────
    testdetails_docs = list(testdetails_collection.find(
        {"test_id": {"$in": list(all_test_ids)}},
        {
            "test_id": 1,
            "specimen_type": 1,
            "collection_container": 1,
            "_id": 0
        }
    ))

    testdetails_map = {
        doc["test_id"]: {
            "specimen_type": doc.get("specimen_type"),
            "collection_container": doc.get("collection_container")
        }
        for doc in testdetails_docs
    }

    # ─────────────────────────────────────────────
    # Fetch Billing Data
    # ─────────────────────────────────────────────
    all_barcodes = list(barcode_tests_map.keys())

    billing_docs = list(billing_collection.find(
        {"barcode": {"$in": all_barcodes}},
        {"barcode": 1, "patient_id": 1, "registrationDate": 1, "_id": 0}
    ))

    barcode_billing_map = {doc["barcode"]: doc for doc in billing_docs}

    # ─────────────────────────────────────────────
    # Fetch Patient Data
    # ─────────────────────────────────────────────
    all_patient_ids = list({
        doc.get("patient_id")
        for doc in billing_docs if doc.get("patient_id")
    })

    patient_docs = list(patient_collection.find(
        {"patient_id": {"$in": all_patient_ids}},
        {"patient_id": 1, "patientname": 1, "age": 1, "gender": 1, "phone": 1, "_id": 0}
    ))

    patient_id_map = {doc["patient_id"]: doc for doc in patient_docs}

    # ─────────────────────────────────────────────
    # Final Response Assembly
    # ─────────────────────────────────────────────
    transferred_samples = []

    for barcode, tests in barcode_tests_map.items():

        # ✅ Attach specimen & container into each test
        enriched_tests = []
        for test in tests:
            test_id = test.get("test_id")
            extra = testdetails_map.get(test_id, {})

            test["specimen_type"] = extra.get("specimen_type", "N/A")
            test["collection_container"] = extra.get("collection_container", "N/A")

            enriched_tests.append(test)

        billing = barcode_billing_map.get(barcode, {})
        patient_id = billing.get("patient_id", "N/A")

        patient = patient_id_map.get(patient_id, {})

        transferred_samples.append({
            "franchise_id": franchise_id,
            "barcode": barcode,
            "patient_id": patient_id,
            "patientname": patient.get("patientname", "N/A"),
            "age": patient.get("age", "N/A"),
            "gender": patient.get("gender", "N/A"),
            "phone": patient.get("phone", "N/A"),
            "registrationDate": str(billing.get("registrationDate")),
            "testdetails": enriched_tests
        })

    client.close()

    return Response({
        "transferred_samples": transferred_samples
    })
     

from .models import Batch
from .serializers import BatchSerializer
@api_view(['POST', 'GET'])
def batch_generation(request):
    if request.method == 'GET':
        try:
            batches = Batch.objects.all().order_by('-created_date')
            serializer = BatchSerializer(batches, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'POST':
        try:
            # Connect to MongoDB
            mongo_url = os.getenv("GLOBAL_DB_HOST")
            client = MongoClient(mongo_url)
            db = client["franchise"]

            diagnostics_db = client["Diagnostics"]
            testdetails_collection = diagnostics_db["core_testdetails"]

            sample_collection = db['franchise_sample']
            franchise_collection = db['franchise_franchise']
            franchise_location_details = db['franchise_location_details']

            # 1. Generate next batch number
            last_batch = Batch.objects.exclude(batch_number=None).order_by('-created_date').first()
            if last_batch and last_batch.batch_number and last_batch.batch_number.isdigit():
                next_number = str(int(last_batch.batch_number) + 1).zfill(5)
            else:
                next_number = "00001"

            data = dict(request.data)
            data['batch_number'] = next_number

            # 2. Parse and deduplicate batch_details
            raw_batch_details = request.data.get("batch_details", [])
            if isinstance(raw_batch_details, str):
                try:
                    raw_batch_details = json.loads(raw_batch_details)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid JSON in batch_details"}, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(raw_batch_details, list):
                return Response({"error": "batch_details must be a list"}, status=status.HTTP_400_BAD_REQUEST)

            seen_barcodes = set()
            unique_batch_list = []
            for item in raw_batch_details:
                if isinstance(item, dict):
                    barcode = item.get("barcode")
                    if barcode and barcode not in seen_barcodes:
                        seen_barcodes.add(barcode)
                        unique_batch_list.append({"barcode": barcode})
            data["batch_details"] = unique_batch_list

            # 3. :wrench: IMPROVED: Collect specimen types using test_id for accurate matching
            franchise_id = data.get('franchise_id')
            specimen_counter = Counter()
           
            if franchise_id:
                batch_barcodes = [item["barcode"] for item in unique_batch_list]
                sample_records = sample_collection.find({
                    "franchise_id": franchise_id,
                    "barcode": {"$in": batch_barcodes}
                })
               
                for record in sample_records:
                    testdetails_raw = record.get("testdetails")
                    if not testdetails_raw:
                        continue

                    testdetails = []
                    try:
                        if isinstance(testdetails_raw, list):
                            testdetails = testdetails_raw
                        elif isinstance(testdetails_raw, str):
                            try:
                                testdetails = json.loads(testdetails_raw)
                            except json.JSONDecodeError:
                                fixed_json = re.sub(r'([{,])(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\2"\3":', testdetails_raw)
                                testdetails = json.loads(fixed_json)
                        elif isinstance(testdetails_raw, dict):
                            testdetails = [testdetails_raw]
                    except Exception as e:
                        print(f"Error parsing testdetails for barcode {record.get('barcode')}: {str(e)}")
                        continue

                    for test in testdetails:
                        if isinstance(test, dict):
                            test_id = test.get("test_id")
                            if test_id:
                                test_obj = testdetails_collection.find_one({"test_id": test_id})
                                if test_obj:
                                    specimen_type = test_obj.get("specimen_type")
                                    if specimen_type:
                                        specimen_counter[specimen_type] += 1
                            else:
                                testname = test.get("testname")
                                if testname:
                                    test_obj = testdetails_collection.find_one({"test_name": testname})
                                    if test_obj:
                                        specimen_type = test_obj.get("specimen_type")
                                        if specimen_type:
                                            specimen_counter[specimen_type] += 1

            data["specimen_count"] = [
                {"specimen_type": specimen_type, "count": count}
                for specimen_type, count in specimen_counter.items()
            ]

            # 4. Get shipment_from from franchise_id -> location_id -> Cluster_Name
            shipment_from_franchise_id = data.get('franchise_id')

            if shipment_from_franchise_id:
                franchise_obj = franchise_collection.find_one({"franchise_id": shipment_from_franchise_id})
                if not franchise_obj:
                    return Response(
                        {"error": f"Invalid shipment_from: franchise_id '{shipment_from_franchise_id}' not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                location_id = franchise_obj.get("location_id")
                if not location_id:
                    return Response(
                        {"error": f"No location_id found for franchise_id '{shipment_from_franchise_id}'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                location_obj = franchise_location_details.find_one({"location_id": location_id})
                if not location_obj or not location_obj.get("Cluster_Name"):
                    return Response(
                        {"error": f"No Cluster_Name found for location_id '{location_id}'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                data["shipment_from"] = location_obj["Cluster_Name"]
            else:
                return Response(
                    {"error": "shipment_from (franchise_id) is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            data["shipment_to"] = "Shanmuga Reference Lab"

            # 5. Save to database
            serializer = BatchSerializer(data=data)
            if serializer.is_valid():
                batch_instance = serializer.save()
               
                print(f"Batch {next_number} created successfully with {len(unique_batch_list)} samples")
                print(f"Specimen count breakdown: {data['specimen_count']}")

                # 6. :white_check_mark: Update batch_number for only Transferred tests in sample_collection
                for item in unique_batch_list:
                    barcode = item.get("barcode")
                    if not barcode:
                        continue

                    sample_doc = sample_collection.find_one({
                        "barcode": barcode,
                        "franchise_id": franchise_id
                    })

                    if sample_doc:
                        testdetails_raw = sample_doc.get("testdetails")
                        try:
                            # Always parse from string
                            if isinstance(testdetails_raw, str):
                                testdetails = json.loads(testdetails_raw)
                            elif isinstance(testdetails_raw, list):
                                testdetails = testdetails_raw
                            else:
                                continue
                        except Exception as e:
                            print(f"Failed to parse testdetails for barcode {barcode}: {e}")
                            continue

                        updated = False
                        for test in testdetails:
                            if (
                                isinstance(test, dict) and
                                test.get("samplestatus") == "Transferred" and
                                test.get("batch_number") in [None, '', 'null']
                            ):
                                test["batch_number"] = next_number
                                updated = True

                        if updated:
                            # Re-serialize testdetails back to string before updating MongoDB
                            sample_collection.update_one(
                                {"_id": sample_doc["_id"]},
                                {"$set": {"testdetails": json.dumps(testdetails)}}
                            )

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import requests
LAB_API_URL = "http://127.0.0.1:1071/_b_a_c_k_e_n_d/LIS/test-values/"
@api_view(['GET'])
def get_test_values(request):
    franchise_id = request.GET.get('locationId')
    date = request.GET.get('date')
    if not franchise_id or not date:
        return Response({"error": "franchise_id and date are required"}, status=400)
    try:
        # :white_check_mark: 1. Fetch test values from external LAB API
        response = requests.get(
            LAB_API_URL,
            params={"locationId": franchise_id, "date": date}
        )
        response.raise_for_status()
        test_data = response.json()
        print(test_data)
        # :white_check_mark: 2. Extract barcode from test_data
        barcode = None
        # if isinstance(test_data, dict) and "data" in test_data and isinstance(test_data["data"], list):
        #     for item in test_data["data"]:
        #         if "barcode" in item:
        #             barcode = item["barcode"]
        #             break
        # if not barcode:
        #     return Response({"error": "No barcode found in test data"}, status=404)
        # :white_check_mark: 3. Connect to MongoDB and get patient_id using barcode
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        franchise_register_collection = db["franchise_register"]
        register_data = franchise_register_collection.find_one({"barcode": barcode})
        if not register_data:
            return Response({"error": "No patient found with barcode: {}".format(barcode)}, status=404)
        patient_id = register_data.get("patient_id")
        # :mag: 3b. Get patient name from franchise_patient using patient_id
        franchise_patient_collection = db["franchise_patient"]
        patient_data = franchise_patient_collection.find_one({"patient_id": patient_id})
        patient_name = patient_data.get("patientname") if patient_data else None
        # :white_check_mark: 4. Return patient_id and test results
        return Response({
            "patient_id": patient_id,
            "patientname": patient_name,
            "barcode": barcode,
            "test_data": test_data
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)



LAB_API_URL = "http://127.0.0.1:1071/_b_a_c_k_e_n_d/LIS/test-values/"
@api_view(['GET'])
def get_patient_by_barcode(request):
    franchise_id = request.GET.get('franchise_id')
    date = request.GET.get('date')
    if not franchise_id or not date:
        return Response({"error": "franchise_id and date are required"}, status=400)
    try:
        # Step 1: Fetch test data from external LAB API
        response = requests.get(
            LAB_API_URL,
            params={"franchise_id": franchise_id, "date": date}
        )
        response.raise_for_status()
        test_data = response.json()
        print(test_data)
        # Step 2: Extract barcode from test_data
        barcode = None
        # if isinstance(test_data, dict) and "data" in test_data:
        #     for item in test_data["data"]:
        #         if "barcode" in item:
        #             barcode = item["barcode"]
        #             break
        # if not barcode:
        #     return Response({"error": "No barcode found in test data"}, status=404)
        # Step 3: Connect to MongoDB and get patient data using barcode
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        register_data = db["franchise_register"].find_one({"barcode": barcode})
        if not register_data:
            return Response({"error": f"No patient found with barcode: {barcode}"}, status=404)
        patient_id = register_data.get("patient_id")
        # Step 4: Fetch patient name from franchise_patient
        patient_data = db["franchise_patient"].find_one({"patient_id": patient_id})
        patient_name = patient_data.get("patientname") if patient_data else None
        # Final response
        return Response({
            "franchise_id": franchise_id,
            "date": date,
            "barcode": barcode,
            "patient_id": patient_id,
            "patientname": patient_name,
            "test_data": test_data
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    

@api_view(["PATCH"])
def cancel_tests(request):
    try:
        patient_id = request.data.get("patient_id")
        created_date_str = request.data.get("created_date")
        test_ids = request.data.get("test_ids")

        if not patient_id or not created_date_str or not test_ids:
            return Response({
                "error": "patient_id, created_date, and test_ids are required"
            }, status=400)

        # Parse created_date
        try:
            created_date = datetime.fromisoformat(
                created_date_str.replace("Z", "+00:00")
            )
        except ValueError:
            return Response({"error": "Invalid created_date format"}, status=400)

        # Find billing record
        billing_record = Billing.objects.filter(
            patient_id=patient_id,
            created_date=created_date
        ).first()

        if not billing_record:
            return Response({
                "error": "No billing record found for the given patient_id and created_date"
            }, status=404)

        # Parse testdetails safely
        test_details = billing_record.testdetails
        if isinstance(test_details, str):
            try:
                test_details = json.loads(test_details)
            except json.JSONDecodeError:
                return Response({"error": "Invalid testdetails JSON format"}, status=400)
        elif not isinstance(test_details, list):
            return Response({"error": "Invalid testdetails format"}, status=400)

        # Ensure test_ids is valid
        if not (test_ids == "all" or isinstance(test_ids, list)):
            return Response({"error": "test_ids must be a list or 'all'"}, status=400)

        # Cancel tests
        cancelled_tests = []
        updated_test_details = []

        for test in test_details:
            t_id = test.get("test_id")

            should_cancel = (
                test_ids == "all" or
                (isinstance(test_ids, list) and t_id in test_ids)
            )

            if should_cancel:
                test["status"] = "Cancel Requested"
                test["cancelled_date"] = timezone.now().isoformat()
                cancelled_tests.append({
                    "test_id": t_id,
                    "test_name": test.get("test_name"),
                    "status": "Cancel Requested"
                })

            updated_test_details.append(test)

        # Save updated testdetails back
        billing_record.testdetails = json.dumps(updated_test_details)
        billing_record.lastmodified_date = timezone.now()
        billing_record.save(update_fields=["testdetails", "lastmodified_date"])

        return Response({
            "message": f"Successfully cancelled {len(cancelled_tests)} test(s)",
            "cancelled_tests": cancelled_tests,
            "patient_id": patient_id,
            "total_tests": len(test_details),
            "updated_testdetails": updated_test_details
        }, status=200)

    except Exception as e:
        return Response({
            "error": f"An error occurred: {str(e)}"
        }, status=500)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_datetime
from pymongo import MongoClient
import os
import json
from bson import ObjectId
from datetime import datetime

mongo_url = os.getenv("GLOBAL_DB_HOST")
client = MongoClient(mongo_url)
db = client["franchise"]
franchise_collection = db["franchise_billing"]

@api_view(["PATCH"])
def test_cancel_request(request):
    """
    PATCH request to update billing status or testdetails for cancellation.
    """
    try:
        patient_id = request.data.get("patient_id")
        created_date_str = request.data.get("created_date")
        test_ids = request.data.get("test_ids", [])

        if not patient_id or not created_date_str:
            return Response(
                {"error": "patient_id and created_date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_date = parse_datetime(created_date_str)
        if not created_date:
            return Response(
                {"error": "Invalid created_date format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        billing = franchise_collection.find_one(
            {"patient_id": patient_id, "created_date": created_date}
        )
        if not billing:
            return Response(
                {"error": "Billing record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Parse testdetails
        testdetails = billing.get("testdetails", [])
        if isinstance(testdetails, str):
            testdetails = json.loads(testdetails)

        updated = False
        for test in testdetails:
            if test_ids and test["test_id"] in test_ids:
                test["status"] = "Cancel Requested"
                updated = True

        if not updated:
            return Response(
                {"error": "No matching tests found to cancel"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        franchise_collection.update_one(
            {"_id": billing["_id"]},
            {
                "$set": {
                    "testdetails": json.dumps(testdetails),
                    "billing_status": "Pending",
                }
            },
        )

        return Response(
            {
                "message": "Cancel request updated successfully",
                "billing_id": str(billing["_id"]),
                "billing_status": "Pending",
                "testdetails": testdetails,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def _normalize_contact(raw):
    """Return digits-only string (no +) or None if invalid."""
    if not raw:
        return None
    s = str(raw)
    # remove spaces, dashes, parentheses, plus
    s = re.sub(r"[ \-\(\)\+]", "", s)
    # keep only digits
    s = "".join(ch for ch in s if ch.isdigit())
    return s or None


import logging
import urllib.parse
import requests
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

@api_view(['POST'])
@csrf_exempt
def send_whatsapp_template(request):
    """
    Accepts JSON:
    {
      contact, name, date, time, product, amount, link, phone, template
    }
    Normalizes contact, validates, builds params and calls provider.
    """
    # parse JSON robustly (accept form fallback)
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        # fallback to POST form fields
        payload = {k: request.POST.get(k) for k in request.POST.keys()} if request.POST else {}

    # Merge with dummy/test fallback if desired (but avoid too-short defaults)
    dummy_contact = getattr(settings, "DEFAULT_TEST_CONTACT", None)
    if dummy_contact and ("contact" not in payload or not payload.get("contact")):
        payload["contact"] = dummy_contact

    # Extract & normalize contact
    contact_raw = payload.get("contact") or payload.get("phone") or payload.get("phoneNumber")
    contact = _normalize_contact(contact_raw)

    if not contact or len(contact) < 8:
        return JsonResponse({
            "error": "Invalid or missing contact. Send international phone number without '+', e.g. 919876543210"
        }, status=400)

    # other fields
    name = payload.get("name", "")
    date = payload.get("date", "")
    time = payload.get("time", "")
    product = payload.get("product", "")
    amount = payload.get("amount", "")
    link = payload.get("link", "")  # expected file_url from upload endpoint
    phone = payload.get("phone") or payload.get("support_phone") or payload.get("franchise_phone") or ""
    template = payload.get("template", "franchise_bill")

    # Build params in the order your WhatsApp template expects ({{1}}..{{7}})
    params_list = [name, date, time, product, amount, link, phone]
    joined = ",".join([str(x) for x in params_list])
    encoded = urllib.parse.quote(joined, safe='')

    api_key = getattr(settings, "BOTIFY_API_KEY", None)
    if not api_key:
        logger.error("BOTIFY_API_KEY not set in settings")
        return JsonResponse({"error": "Server misconfiguration: BOTIFY_API_KEY missing"}, status=500)

    endpoint = (
        f"https://dashboard.botify.in/api/v1/external/sendtemplatemessage"
        f"?apikey={urllib.parse.quote(api_key, safe='')}"
        f"&contact={urllib.parse.quote(contact, safe='')}"
        f"&template={urllib.parse.quote(str(template), safe='')}"
        f"&params={encoded}"
    )

    try:
        resp = requests.get(endpoint, timeout=15)
    except requests.RequestException as e:
        logger.exception("Botify API error")
        return JsonResponse({"error": "Provider error", "details": str(e)}, status=502)

    try:
        provider_json = resp.json()
    except ValueError:
        provider_json = {"raw": resp.text}

    # Helpful response to the frontend
    return JsonResponse({
        "status_code": resp.status_code,
        "provider_response": provider_json,
        "sent_payload": {
            "contact": contact,
            "name": name,
            "date": date,
            "time": time,
            "product": product,
            "amount": amount,
            "link": link,
            "phone": phone,
            "template": template
        }
    }, status=200 if resp.ok else 502)


# MongoDB Connection
client = MongoClient(os.getenv('GLOBAL_DB_HOST'))
db = client["franchise"]
fs = gridfs.GridFS(db)

@api_view(['POST'])
@csrf_exempt
# @permission_classes([HasRoleAndDataPermission])
def upload_pdf_to_gridfs(request):
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]

        # 1. Validate type
        if file.content_type != "application/pdf":
            return JsonResponse({"error": "Only PDF files are allowed."}, status=400)

        # 2. Limit size (5MB)
        if file.size > 5 * 1024 * 1024:
            return JsonResponse({"error": "File too large (max 5 MB)."}, status=400)

        # 3. Sanitize filename
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_\.\-]', '_', file.name)

        # 4. Upload to GridFS
        file_id = fs.put(file, filename=safe_name)

        # 5. Generate access URL
        file_url = f"http://127.0.0.1:8190/_b_a_c_k_e_n_d/franchiseapp/get-file/{str(file_id)}"

        return JsonResponse({"file_id": str(file_id), "file_url": file_url})

    return JsonResponse({"error": "No file uploaded"}, status=400)

from django.http import HttpResponse
from bson import ObjectId

@api_view(['GET'])
@csrf_exempt
# @permission_classes([ HasRoleAndDataPermission])
def get_pdf_from_gridfs(request, file_id):
    try:
        file = fs.get(ObjectId(file_id))
        response = HttpResponse(file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{file.filename}"'  # ← forces download
        return response
    except:
        return JsonResponse({"error": "File not found"}, status=404)



import os
import json
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes

from pymongo import MongoClient

# If you already have HasRolePermission imported, keep it.


def get_mongo_db():
    """Helper to get MongoDB 'franchise' database."""
    mongo_url = os.getenv("GLOBAL_DB_HOST")  # same as you used
    client = MongoClient(mongo_url)
    db = client["franchise"]
    return client, db


@api_view(["POST"])
@csrf_exempt
def request_password_reset(request):
    """
    POST JSON: { "franchise_id": "SHF001" }

    1) Find franchise in franchise_franchise.
    2) Find related user in franchise_user.
    3) Generate reset_token + expiry.
    4) Save in franchise_user.
    5) Send reset email with link: /reset-password/?token=...&franchise_id=...
    """
    try:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            data = request.POST

        franchise_id = data.get("franchise_id")
        if not franchise_id:
            return JsonResponse({"error": "franchise_id is required"}, status=400)

        client, db = get_mongo_db()
        franchise_collection = db["franchise_franchise"]
        user_collection = db["franchise_user"]

        # 1) Find franchise record for email
        franchise = franchise_collection.find_one({"franchise_id": franchise_id})
        if not franchise:
            return JsonResponse(
                {"error": f"Franchise with ID {franchise_id} not found"},
                status=404,
            )

        franchise_email = franchise.get("email")
        franchise_name = franchise.get("franchise_name", franchise_id)

        if not franchise_email:
            return JsonResponse(
                {"error": f"No email set for franchise {franchise_id}"},
                status=400,
            )

        # 2) Find user record for this franchise_id
        user = user_collection.find_one({"franchise_id": franchise_id})
        if not user:
            return JsonResponse(
                {"error": f"No franchise_user found for {franchise_id}"},
                status=404,
            )

        # 3) Generate token + expiry (e.g., 1 hour)
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # 4) Update user with token & expiry & flag
        user_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "reset_token": reset_token,
                    "reset_token_expires": expires_at,
                    "reset_password": True,
                    "lastmodified_date": datetime.utcnow(),
                    "lastmodified_by": franchise_id,
                }
            },
        )

        # 5) Build reset URL
        reset_path = reverse("reset_password_form")
        reset_url = request.build_absolute_uri(
            f"{reset_path}?token={reset_token}&franchise_id={franchise_id}"
        )

        # 6) Send email
        subject = "Reset Your Password - Shanmuga Diagnostics"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "parthibansmrft@gmail.com")

        # Plain text version
        text_body = f"""
Dear {franchise_name},

We received a request to reset your password for your Shanmuga Diagnostics franchise account (ID: {franchise_id}).

To reset your password, please click the link below:
{reset_url}

This link will expire in 1 hour for security reasons.

If you did not request this password reset, please ignore this email or contact our support team immediately.

Best regards,
Shanmuga Diagnostics Team
"""

        # Modern HTML version
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Password Reset</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#f4f7fa;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f4f7fa;padding:40px 20px;">
        <tr>
            <td align="center">
                <!-- Main Container -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px;background-color:#ffffff;border-radius:16px;box-shadow:0 4px 12px rgba(0,0,0,0.08);overflow:hidden;">
                    
                    <!-- Header with gradient -->
                    <tr>
                        <td style="background:linear-gradient(135deg, #6FB1C4 0%, #4B9EB0 100%);padding:40px 40px 30px;text-align:center;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td align="center">
                                        <!-- Logo placeholder - replace with your logo URL -->
                                        <div style="background:#ffffff;width:70px;height:70px;border-radius:16px;margin:0 auto 20px;display:inline-flex;align-items:center;justify-content:center;box-shadow:0 8px 20px rgba(0,0,0,0.12);">
                                            <span style="font-size:32px;">🔐</span>
                                        </div>
                                        <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;letter-spacing:-0.5px;">Password Reset Request</h1>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding:40px 40px 30px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td style="color:#2d3748;font-size:16px;line-height:1.6;">
                                        <p style="margin:0 0 16px;font-size:18px;font-weight:600;color:#1a202c;">Hello {franchise_name},</p>
                                        <p style="margin:0 0 24px;color:#4a5568;">We received a request to reset the password for your Shanmuga Diagnostics franchise account.</p>
                                        
                                        <!-- Info Box -->
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f7fafc;border-radius:12px;margin:0 0 24px;">
                                            <tr>
                                                <td style="padding:20px;">
                                                    <p style="margin:0 0 8px;font-size:13px;color:#718096;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Franchise ID</p>
                                                    <p style="margin:0;font-size:18px;color:#2d3748;font-weight:700;font-family:monospace;">{franchise_id}</p>
                                                </td>
                                            </tr>
                                        </table>
                                        
                                        <p style="margin:0 0 28px;color:#4a5568;">Click the button below to reset your password. This link will expire in <strong>1 hour</strong> for security reasons.</p>
                                    </td>
                                </tr>
                                
                                <!-- Button -->
                                <tr>
                                    <td align="center" style="padding:0 0 32px;">
                                        <a href="{reset_url}" style="display:inline-block;background:linear-gradient(135deg, #6FB1C4 0%, #4B9EB0 100%);color:#ffffff;text-decoration:none;padding:16px 48px;border-radius:12px;font-weight:600;font-size:16px;box-shadow:0 4px 14px rgba(75,158,176,0.3);transition:all 0.3s ease;">Reset Password</a>
                                    </td>
                                </tr>
                                
                                <!-- Alternative Link -->
                                <tr>
                                    <td style="padding:0 0 24px;border-top:1px solid #e2e8f0;padding-top:24px;">
                                        <p style="margin:0 0 12px;color:#718096;font-size:14px;">Or copy and paste this link into your browser:</p>
                                        <p style="margin:0;word-break:break-all;">
                                            <a href="{reset_url}" style="color:#4B9EB0;text-decoration:none;font-size:13px;">{reset_url}</a>
                                        </p>
                                    </td>
                                </tr>
                                
                                <!-- Security Notice -->
                                <tr>
                                    <td style="background:#fef5e7;border-left:4px solid #f39c12;border-radius:8px;padding:20px;">
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                            <tr>
                                                <td width="30" valign="top">
                                                    <span style="font-size:20px;">⚠️</span>
                                                </td>
                                                <td style="color:#856404;font-size:14px;line-height:1.5;">
                                                    <strong style="display:block;margin-bottom:4px;">Security Notice</strong>
                                                    If you didn't request this password reset, please ignore this email or contact our support team immediately.
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background:#f8fafc;padding:32px 40px;text-align:center;border-top:1px solid #e2e8f0;">
                            <p style="margin:0 0 12px;color:#64748b;font-size:14px;">Need help? Contact our support team</p>
                            <p style="margin:0 0 16px;">
                                <a href="mailto:support@shanmugadiagnostics.com" style="color:#4B9EB0;text-decoration:none;font-weight:600;font-size:14px;">support@shanmugadiagnostics.com</a>
                            </p>
                            <p style="margin:0;color:#94a3b8;font-size:13px;">© 2025 Shanmuga Diagnostics. All rights reserved.</p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        msg = EmailMultiAlternatives(subject, text_body, from_email, [franchise_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()

        return JsonResponse(
            {
                "status": "ok",
                "message": "Reset link sent successfully",
                "franchise_id": franchise_id,
                "email": franchise_email,
            },
            status=200,
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Error in request_password_reset")
        return JsonResponse(
            {"error": "Internal server error", "details": str(e)}, status=500
        )
    finally:
        try:
            client.close()
        except Exception:
            pass




@api_view(["GET"])
def reset_password_form(request):
    """Display password reset form"""
    token = request.GET.get('token')
    franchise_id = request.GET.get('franchise_id')  # Changed from employee_id
    
    if not token or not franchise_id:
        return render(request, 'email/error.html', {
            'error': 'Invalid reset link. Token and franchise ID are required.'
        })
    
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    franchise_user_collection = db["franchise_user"]
    
    try:
        user = franchise_user_collection.find_one({
            "franchise_id": franchise_id,
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })
        
        if not user:
            return render(request, 'email/error.html', {
                'error': 'Invalid or expired reset token. Please request a new password reset link.'
            })
        
        context = {
            'token': token,
            'franchise_id': franchise_id,
            'email': user.get('email', '')
        }
        
        return render(request, 'email/reset_password.html', context)
        
    except Exception as e:
        return render(request, 'email/error.html', {
            'error': f'An error occurred: {str(e)}'
        })
    finally:
        client.close()

from django.contrib.auth.hashers import make_password

@api_view(["POST"])
@csrf_exempt
def confirm_reset_password(request):
    """
    Handle POST from reset_password.html:
    Fields: token, franchise_id, new_password, confirm_password
    """
    token = request.POST.get("token")
    franchise_id = request.POST.get("franchise_id")
    new_password = request.POST.get("new_password")
    confirm_password = request.POST.get("confirm_password")

    if not token or not franchise_id:
        return render(request, "email/error.html", {
            "error": "Invalid request. Missing token or franchise ID."
        })

    if not new_password or not confirm_password:
        return render(request, "email/error.html", {
            "error": "Both password fields are required."
        })

    if new_password != confirm_password:
        return render(request, "email/error.html", {
            "error": "Passwords do not match. Please try again."
        })

    try:
        client, db = get_mongo_db()
        user_collection = db["franchise_user"]

        # validate token again
        user = user_collection.find_one({
            "franchise_id": franchise_id,
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })

        if not user:
            return render(request, "email/error.html", {
                "error": "Invalid or expired reset token. Please request a new password reset link."
            })

        # hash new password using Django's hasher
        hashed_password = make_password(new_password)

        # update user: set password, clear token fields, reset flag
        user_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password": hashed_password,
                    "reset_password": False,
                    "lastmodified_date": datetime.utcnow(),
                    "lastmodified_by": franchise_id,
                },
                "$unset": {
                    "reset_token": "",
                    "reset_token_expires": "",
                }
            },
        )

        # success page
        return render(request, "email/reset_success.html", {
            "franchise_id": franchise_id,
            "email": user.get("email", ""),
        })

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Error in confirm_reset_password")
        return render(request, "email/error.html", {
            "error": f"An error occurred: {str(e)}"
        })
    finally:
        try:
            client.close()
        except Exception:
            pass



@api_view(['GET', 'POST'])
@csrf_exempt
def refby(request):
    if request.method == 'POST':
        serializer = RefBySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'GET':
        franchise_id = request.query_params.get('franchise_id')
        if franchise_id:
            collectors = RefBy.objects.filter(franchise_id=franchise_id)
        else:
            collectors = RefBy.objects.all()
        serializer = RefBySerializer(collectors, many=True)
        return Response(serializer.data)

from decimal import Decimal
from rest_framework.decorators import api_view
from rest_framework.response import Response

from decimal import Decimal
from bson.decimal128 import Decimal128
from rest_framework.decorators import api_view
from rest_framework.response import Response
from decimal import Decimal
from bson.decimal128 import Decimal128  # <= important

def to_decimal(value, default='0.00'):
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    # fallback: string/number
    return Decimal(str(value))

@api_view(['GET'])
def get_due_patients(request):
    franchise_id = request.GET.get('franchise_id')
    barcode = request.GET.get('barcode')  # optional

    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)

    try:
        qs = Billing.objects.filter(franchise_id=franchise_id).order_by('-registrationDate')
        if barcode:
            qs = qs.filter(barcode=barcode)

        due_patients = []

        for bill in qs:
            # always convert DB values to Decimal
            net_amount = to_decimal(bill.netAmount)

            paid_amount = Decimal('0.00')
            payment_mode = bill.paymentMode

            # Case 1: Explicit "Due" string -> nothing paid
            if payment_mode == "Due":
                paid_amount = Decimal('0.00')

            # Case 2: List of payment dicts (already parsed JSON)
            elif isinstance(payment_mode, list):
                for p in payment_mode:
                    if isinstance(p, dict) and p.get('mode') != 'Due':
                        try:
                            paid_amount += to_decimal(p.get('amount', 0))
                        except Exception:
                            pass

            # Case 3: Non-empty, non-list, non-"Due" (e.g. "Cash", "Card")
            elif payment_mode:
                paid_amount = net_amount

            # now both are Decimal (not Decimal128)
            due_amount = net_amount - paid_amount

            if due_amount > Decimal('0.01'):
                patient_info = {}
                try:
                    patient = bill.patient
                    patient_info = {
                        "patient_id": getattr(patient, "patient_id", None),
                        "patientname": getattr(patient, "patientname", None),
                        "phoneNumber": getattr(patient, "phoneNumber", None),
                    }
                except Exception:
                    patient_info = {
                        "patient_id": getattr(bill, "patient_id", None),
                        "patientname": getattr(bill, "patientname", None),
                        "phoneNumber": getattr(bill, "phoneNumber", None),
                    }

                due_patients.append({
                    "barcode": bill.barcode,
                    "registrationDate": bill.registrationDate,
                    "netAmount": str(net_amount),
                    "paid_amount": str(paid_amount),
                    "due_amount": str(due_amount),
                    "patient_info": patient_info,
                    "due_update_date": bill.due_update_date.isoformat() if bill.due_update_date else None,
                    "payments": bill.payments if isinstance(bill.payments, list) else []
                })

        return Response(due_patients, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


from rest_framework.decorators import api_view
from rest_framework.response import Response

from decimal import Decimal
from bson.decimal128 import Decimal128
from collections import defaultdict

def to_decimal(value):
    """Convert Mongo Decimal128 or other numeric types to Python Decimal."""
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


@api_view(['GET'])
def get_accounts_summary(request):
    franchise_id = request.GET.get("franchise_id")
    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)

    # Filter by franchise - use values to avoid loading problematic JSONFields
    queryset = Billing.objects.filter(
        franchise_id=franchise_id,
        registrationDate__isnull=False
    ).order_by('registrationDate').values('registrationDate', 'netAmount')

    # Monthly grouping in Python
    # key: (year, month) -> { patient_count, total_billed, franchise_share }
    monthly_map = defaultdict(lambda: {
        "patient_count": 0,
        "total_billed": Decimal('0'),
        "franchise_share": Decimal('0')
    })

    overall_total = Decimal('0')
    overall_share = Decimal('0')

    # 1. Calculate from Billing (for patient count and total billed)
    for bill in queryset:
        dt = bill['registrationDate']
        if not dt:
            continue

        key = (dt.year, dt.month)
        amount = to_decimal(bill['netAmount'])

        monthly_map[key]["patient_count"] += 1
        monthly_map[key]["total_billed"] += amount
        overall_total += amount

    # 2. Fetch FranchiseMonthlyRevenue for share
    revenue_records = FranchiseMonthlyRevenue.objects.filter(franchise_id=franchise_id).values('year', 'month', 'franchise_share')
    for rev in revenue_records:
        key = (rev['year'], rev['month'])
        share = to_decimal(rev['franchise_share'])
        monthly_map[key]["franchise_share"] = share
    
    # Recalculate overall_share to be safe (sum of all unique monthly shares)
    overall_share = sum(monthly_map[k]["franchise_share"] for k in monthly_map)

    # Format the response
    sorted_keys = sorted(monthly_map.keys(), reverse=True)

    formatted_data = []
    for year, month in sorted_keys:
        sample_date_str = f"{year}-{month:02d}-01"
        from datetime import datetime
        sample_date = datetime.strptime(sample_date_str, "%Y-%m-%d")

        data = monthly_map[(year, month)]
        formatted_data.append({
            "month": sample_date.strftime("%B %Y"),
            "year": year,
            "month_num": month,
            "patient_count": data["patient_count"],
            "total_billed": str(data["total_billed"]),
            "franchise_share": str(data["franchise_share"])
        })

    return Response({
        "monthly_data": formatted_data,
        "overall_total": str(overall_total),
        "overall_share": str(overall_share)
    }, status=200)


from datetime import datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response

# assuming to_decimal is already defined above, as in your previous code

@api_view(['GET'])
def get_monthly_billing_details(request):
    franchise_id = request.GET.get("franchise_id")
    month = request.GET.get("month")
    year = request.GET.get("year")
    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")

    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)
    
    try:
        if from_date_str and to_date_str:
            start_date = datetime.strptime(from_date_str, "%Y-%m-%d")
            # For end date, if it's just a date, we might want to include the whole day. 
            # But usually from frontend it sends YYYY-MM-DD. 
            # If we want inclusive, we should set time to max or add 1 day.
            # Let's assume inclusive for the day.
            end_date = datetime.strptime(to_date_str, "%Y-%m-%d") + timedelta(days=1)
        elif month and year:
            month = int(month)
            year = int(year)
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
        else:
             return Response({"error": "Either (month, year) or (from_date, to_date) are required"}, status=400)

        # Use range filter instead of __year / __month
        billings = (
            Billing.objects
            .filter(
                franchise_id=franchise_id,
                registrationDate__gte=start_date,
                registrationDate__lt=end_date,
            )
            .order_by('-registrationDate')
            .values(
                'registrationDate',
                'netAmount',
                'barcode',
                'billing_status',
                'patient__patientname',
            )
        )

        data = []
        for b in billings:
            reg_date = b.get('registrationDate')
            if not reg_date:
                continue

            patient_name = b.get('patient__patientname') or "Unknown"

            data.append({
                "date": reg_date.strftime("%Y-%m-%d"),
                "patient_name": patient_name,
                "amount": str(to_decimal(b['netAmount'])),
                "barcode": b['barcode'],
                "status": b['billing_status'],
            })

        return Response(data, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)

import csv
@api_view(['GET'])
def export_accounts_csv(request):
    franchise_id = request.GET.get("franchise_id")
    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")

    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)
    
    try:
        if from_date_str and to_date_str:
            start_date = datetime.strptime(from_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(to_date_str, "%Y-%m-%d") + timedelta(days=1)
        else:
             # Default to current month if not provided
            now = datetime.now()
            start_date = datetime(now.year, now.month, 1)
            if now.month == 12:
                end_date = datetime(now.year + 1, 1, 1)
            else:
                end_date = datetime(now.year, now.month + 1, 1)

        billings = (
            Billing.objects
            .filter(
                franchise_id=franchise_id,
                registrationDate__gte=start_date,
                registrationDate__lt=end_date,
            )
            .order_by('-registrationDate')
            .values(
                'registrationDate',
                'netAmount',
                'barcode',
                'billing_status',
                'patient__patientname',
            )
        )

        response = HttpResponse(content_type='text/csv')
        filename = f"Accounts_Report_{start_date.strftime('%Y-%m-%d')}_to_{to_date_str if to_date_str else 'end'}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Date', 'Patient Name', 'Barcode', 'Status', 'Amount'])

        total_amount = Decimal('0.00')

        for b in billings:
            reg_date = b.get('registrationDate')
            if not reg_date:
                continue

            patient_name = b.get('patient__patientname') or "Unknown"
            amount = to_decimal(b['netAmount'])
            total_amount += amount

            writer.writerow([
                reg_date.strftime("%Y-%m-%d"),
                patient_name,
                b['barcode'],
                b['billing_status'],
                amount
            ])
        
        # Add Total Row
        writer.writerow([])
        writer.writerow(['TOTAL', '', '', '', total_amount])

        return response

    except Exception as e:
        return Response({"error": str(e)}, status=500)


