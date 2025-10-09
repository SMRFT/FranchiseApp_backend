from django.db import models

class Franchise(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
    ]

    franchise_id = models.CharField(max_length=100, primary_key=True)
    franchise_name = models.CharField(max_length=100)
    location_id = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=15)
    email = models.EmailField()
    alt_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField()
    qualification = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    pincode = models.CharField(max_length=10)
    dob = models.DateField(null=True, blank=True)
    initialpayment = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)

    createdby = models.CharField(max_length=100)
    lastmodifiedby = models.CharField(max_length=100, blank=True, null=True)
    createddate = models.DateTimeField(auto_now_add=True)
    lastmodifieddate = models.DateTimeField(auto_now=True)



    # File IDs
    aadhaar_file_id = models.CharField(max_length=100, blank=True, null=True)
    payment_file_id = models.CharField(max_length=100, blank=True, null=True)
    agreement_file_id = models.CharField(max_length=100, blank=True, null=True)
    franchise_photo_file_id = models.CharField(max_length=100, blank=True, null=True)



    def __str__(self):
        return self.franchise_name




from djongo import models  
class BarcodeRange(models.Model):
    _id = models.ObjectIdField()  
    franchise_id = models.CharField(max_length=100)
    startbarcode = models.CharField(max_length=100)
    endbarcode = models.CharField(max_length=100)
    createddate = models.DateTimeField(auto_now_add=True)
    createdby = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
     

    def __str__(self):
        return f"{self.startbarcode} - {self.endbarcode} by {self.createdby}"
    


from bson import ObjectId
from django.db import models

class Wallet(models.Model):
    wallet_id = models.CharField(primary_key=True, max_length=50, default=lambda: str(ObjectId()))
    
    franchise = models.OneToOneField(  # One wallet per franchise
        'Franchise',
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='INR')  # Removed unique
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.franchise.franchise_name} - ₹{self.balance}"



class barcodestock(models.Model):
    startbarcode = models.CharField(max_length=100)
    endbarcode = models.CharField(max_length=100)
    createddate = models.DateTimeField(auto_now_add=True)
    createdby = models.CharField(max_length=100)

from bson import ObjectId
from django.db import models

class Wallet(models.Model):
    wallet_id = models.CharField(primary_key=True, max_length=50, default=lambda: str(ObjectId()))
    
    franchise = models.OneToOneField(  # One wallet per franchise
        'Franchise',
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='INR')  # Removed unique
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.franchise.franchise_name} - ₹{self.balance}"


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
    currency_id = models.CharField(max_length=100,default='INR')
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    wallet_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    user_notes = models.TextField(blank=True)
    system_notes = models.TextField(blank=True)
    payment_gateway_id = models.IntegerField(default=2)
    payment_gateway_ref_id = models.CharField(max_length=200, blank=True)
    payment_gateway_txn_id = models.CharField(max_length=200, blank=True)
    payment_gateway_status = models.CharField(max_length=50, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_id} - ₹{self.payment_amount}"

    class Meta:
        ordering = ['-created']
