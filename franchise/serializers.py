from rest_framework import serializers
from .models import Franchise,BarcodeRange,Wallet
from bson import ObjectId
from .models import Wallet, Payments
from bson import ObjectId
from decimal import Decimal
import uuid

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):    
        return ObjectId(data)

class FranchiseSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)

    class Meta:
        model = Franchise
        fields = '__all__'

    def create(self, validated_data):
        # Create Franchise
        franchise = super().create(validated_data)

        # Create Wallet
        wallet = Wallet.objects.create(
            franchise_id=franchise.franchise_id,
            balance=Decimal('2500.00'),  # Default initial balance
            currency='INR'
        )

        # Create Initial Payment Entry
        Payments.objects.create(
            transaction_id=str(uuid.uuid4()),
            wallet=wallet,
            transaction_type='initial',
            payment_amount=Decimal('2500.00'),
            wallet_amount=Decimal('2500.00'),
            status='success',
            user_notes='Initial funding',
            system_notes='Auto-created during franchise registration'
        )

        return franchise


class BarcodeRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarcodeRange
        fields = '__all__'  # keep all original fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(instance, '_id'):
            data['_id'] = str(instance._id)  # include ObjectId
        return data
    

# serializers.py
from rest_framework import serializers
from .models import barcodestock

class BarcodestockSerializer(serializers.ModelSerializer):
    class Meta:
        model =barcodestock
        fields = '__all__'



