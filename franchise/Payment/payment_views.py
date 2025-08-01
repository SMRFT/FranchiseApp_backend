from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
import uuid
from datetime import datetime
from decimal import Decimal

# Models and serializers
from .payment_models import Wallet, Payments, Currency, PaymentGateway
from .payment_serializers import PaymentSerializer, WalletSerializer

def safe_float(val):
    try:
        return float(val.to_decimal() if hasattr(val, 'to_decimal') else val)
    except Exception:
        return 0.0

@api_view(['GET'])
def get_payment_gateways(request):
    """Get all active payment gateways"""
    try:
        gateways = PaymentGateway.objects.filter(status='active')
        gateways_data = [{
            'id': gateway.payment_gateway_id,
            'name': gateway.name,
            'description': gateway.description,
            'status': gateway.status
        } for gateway in gateways]
        
        return Response({'payment_gateways': gateways_data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_currencies(request):
    """Get all active currencies"""
    try:
        currencies = Currency.objects.filter(status='active')
        currencies_data = [{
            'code': currency.short_code,
            'name': currency.name,
            'description': currency.description,
            'status': currency.status
        } for currency in currencies]
        
        return Response({'currencies': currencies_data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_wallet_balance(request, franchise_id):
    try:
        # Fetch wallet only if status is 'active'
        wallet = Wallet.objects.filter(franchise_id=franchise_id, status='active').first()
        
        if not wallet:
            return Response({'error': 'Active wallet not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'total_balance': safe_float(wallet.balance),
            'franchiser_share': safe_float(wallet.franchiser_share),
            'franchise_share': safe_float(wallet.franchise_share),
            'currency': "INR"  # Hardcoded since wallet has no currency field
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_payment_history(request, franchise_id):
    try:
        wallet = get_object_or_404(Wallet, franchise_id=franchise_id)
        payments = Payments.objects.filter(wallet=wallet).order_by('-created')[:20]

        def safe_decimal(val):
            return float(val.to_decimal() if hasattr(val, 'to_decimal') else val)

        payments_data = []
        for p in payments:
            payments_data.append({
                'reference_id': p.transaction_id,
                'amount': safe_decimal(p.payment_amount),
                'status': p.status,
                'transaction_type': p.transaction_type,
                'created_at': p.created.isoformat(),
                'payment_gateway_ref_id': p.payment_gateway_ref_id,
                'payment_gateway_name': getattr(p.payment_gateway, 'name', ''),  # Safe access
                'currency': getattr(p.currency, 'short_code', '')  # Safe access
            })

        return Response({'payments': payments_data})

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def save_payment(request):
    try:
        data = request.data
        
        with transaction.atomic():
            # Ensure required fields exist
            required_fields = ['franchise_id', 'reference_id', 'amount', 'status', 'payment_gateway_id', 'currency_code']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return Response({
                    'error': f'Missing fields: {", ".join(missing_fields)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get or create Wallet
            wallet, created = Wallet.objects.get_or_create(
                franchise_id=data['franchise_id'],
                defaults={'balance': Decimal('0.00')}
            )
            
            # Get Payment Gateway
            try:
                payment_gateway = PaymentGateway.objects.get(payment_gateway_id=data['payment_gateway_id'])

            except PaymentGateway.DoesNotExist:
                return Response({
                    'error': 'Payment gateway not found'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get currency
            try:
                currency = Currency.objects.get(short_code=data['currency_code'])
            except Currency.DoesNotExist:
                return Response({
                    'error': 'Currency not found'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse amount safely
            amount = Decimal(str(data['amount']))
            
            # Create Payment
            payment = Payments.objects.create(
                transaction_id=data['reference_id'],
                wallet=wallet,
                transaction_type=data.get('payment_type', 'topup'),
                currency=currency,
                payment_amount=amount,
                wallet_amount=amount,
                status=data['status'],
                payment_gateway=payment_gateway,
                payment_gateway_ref_id=data.get('payment_id', ''),
                payment_gateway_txn_id=data.get('order_id', ''),
                payment_gateway_status=data['status'],
                system_notes=f"Payment via {payment_gateway.name} - {data.get('signature', '')}",
                user_notes=f"Franchise: {data.get('franchise_name', '')}"
            )
            
            # Update wallet if payment is successful
            if data['status'] == 'success':
                current_balance = wallet.balance.to_decimal() if hasattr(wallet.balance, "to_decimal") else wallet.balance
                wallet.balance = Decimal(str(current_balance)) + amount
                wallet.save()
            
            return Response({'message': 'Payment saved successfully'})
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def add_wallet_balance(request):
    try:
        data = request.data
        
        with transaction.atomic():
            wallet = get_object_or_404(Wallet, franchise_id=data['franchise_id'])
            transaction_id = f"WALLET_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            currency = Currency.objects.get(short_code=data.get('currency_code', 'INR'))
            payment_gateway = PaymentGateway.objects.get(name='Manual')
            
            Payments.objects.create(
                transaction_id=transaction_id,
                wallet=wallet,
                transaction_type=data['transaction_type'],
                currency=currency,
                payment_amount=Decimal(str(data['amount'])),
                wallet_amount=Decimal(str(data['amount'])),
                status='success',
                payment_gateway=payment_gateway,
                system_notes="Manual wallet balance addition"
            )
            
            if data['transaction_type'] == 'credit':
                wallet.balance += Decimal(str(data['amount']))
            else:
                wallet.balance -= Decimal(str(data['amount']))
            
            wallet.save()
            
            return Response({'message': 'Wallet balance updated successfully'})
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
