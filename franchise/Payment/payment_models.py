from django.db import models
from django.utils import timezone
import uuid

from django.db import models
from django.utils import timezone
import uuid
from decimal import Decimal

class Currency(models.Model):
    short_code = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, 
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.short_code})"

from bson import ObjectId  # if needed

class PaymentGateway(models.Model):
    payment_gateway_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

from bson import ObjectId
class Wallet(models.Model):
    wallet_id = models.CharField(primary_key=True, max_length=50, default=lambda: str(ObjectId()))
    franchise_id = models.CharField(max_length=100, unique=True)  # REPLACE Franchise FK
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency =  models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.franchise_id} - ₹{self.balance}"

    @property
    def franchiser_share(self):
        return Decimal(str(self.balance)) * Decimal("0.70")

    @property
    def franchise_share(self):
        return Decimal(str(self.balance)) * Decimal("0.30")



class Payments(models.Model):
    TRANSACTION_TYPES = [
        ('initial', 'Initial Payment'),
        ('topup', 'Top Up'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    transaction_id = models.CharField(max_length=100, primary_key=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    wallet_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    user_notes = models.TextField(blank=True)
    system_notes = models.TextField(blank=True)
    payment_gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    payment_gateway_ref_id = models.CharField(max_length=200, blank=True)
    payment_gateway_txn_id = models.CharField(max_length=200, blank=True)
    payment_gateway_status = models.CharField(max_length=50, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_id} - ₹{self.payment_amount}"

    class Meta:
        ordering = ['-created']
