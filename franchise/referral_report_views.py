from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Billing
from collections import defaultdict
from decimal import Decimal
from bson.decimal128 import Decimal128
from datetime import datetime

def to_decimal(value):
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))

@api_view(['GET'])
def get_referral_report(request):
    franchise_id = request.GET.get('franchise_id')
    month = request.GET.get('month')
    year = request.GET.get('year')

    if not franchise_id or not month or not year:
        return Response({"error": "franchise_id, month, and year are required"}, status=400)

    try:
        month = int(month)
        year = int(year)

        # Build start and end of the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        billings = Billing.objects.filter(
            franchise_id=franchise_id,
            registrationDate__gte=start_date,
            registrationDate__lt=end_date
        ).values('referredDoctor', 'netAmount')

        report = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})

        for b in billings:
            doc = b['referredDoctor']
            if not doc:
                doc = "Unknown"
            
            report[doc]['count'] += 1
            report[doc]['amount'] += to_decimal(b['netAmount'])

        data = []
        for doc, stats in report.items():
            data.append({
                'doctor': doc,
                'patients': stats['count'],
                'amount': str(stats['amount'])
            })

        return Response(data, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)