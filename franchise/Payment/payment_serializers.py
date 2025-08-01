from rest_framework import serializers
from .payment_models import Payments, Wallet, Currency, PaymentGateway

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payments
        fields = '__all__'

class WalletSerializer(serializers.ModelSerializer):
    franchiser_share = serializers.ReadOnlyField()
    franchise_share = serializers.ReadOnlyField()
    
    class Meta:
        model = Wallet
        fields = '__all__'

