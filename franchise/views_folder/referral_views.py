from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Billing
from datetime import datetime
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
def get_referral_report(request):
    franchise_id = request.GET.get("franchise_id")
    month = request.GET.get("month")
    year = request.GET.get("year")

    if not franchise_id:
        return Response({"error": "franchise_id is required"}, status=400)

    try:
        # Base query
        queryset = Billing.objects.filter(franchise_id=franchise_id)

        # Optional month/year filter
        if month and year:
            try:
                month = int(month)
                year = int(year)
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month + 1, 1)

                queryset = queryset.filter(
                    registrationDate__gte=start_date,
                    registrationDate__lt=end_date
                )
            except ValueError:
                return Response({"error": "Invalid month or year format"}, status=400)

        # Group in Python: key = doctor name
        referral_map = defaultdict(lambda: {
            "patient_count": 0,
            "total_amount": Decimal('0')
        })

        for bill in queryset:
            doctor_name = bill.referredDoctor or "Self / None"
            amount = to_decimal(bill.netAmount)

            referral_map[doctor_name]["patient_count"] += 1
            referral_map[doctor_name]["total_amount"] += amount

        # Convert to sorted list (by total_amount desc)
        data = []
        for doctor_name, agg in referral_map.items():
            data.append({
                "doctor_name": doctor_name,
                "patient_count": agg["patient_count"],
                "total_amount": str(agg["total_amount"]),
            })

        data.sort(key=lambda x: Decimal(x["total_amount"]), reverse=True)

        return Response(data, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)
