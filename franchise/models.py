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

    createdby = models.CharField(max_length=100 ,blank=True, null=True)
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
    barcode_id = models.CharField(max_length=100, unique=True, blank=True)
    startbarcode = models.CharField(max_length=100)
    endbarcode = models.CharField(max_length=100)
    date = models.DateTimeField(auto_now_add=True)
    createddate = models.DateTimeField(auto_now_add=True)
    createdby = models.CharField(max_length=100)
    modifedby = models.CharField(max_length=100, null=True, blank=True)
    modifieddatetime = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        if not self.barcode_id:
            last_obj = barcodestock.objects.order_by('-createddate').first()

            if last_obj and last_obj.barcode_id:
                try:
                    last_number = int(last_obj.barcode_id.replace("BC", ""))
                    next_number = last_number + 1
                except:
                    next_number = 1
            else:
                next_number = 1

            self.barcode_id = f"BC{next_number:05d}"

        super().save(*args, **kwargs)

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



from django.db import models


class FranchiseLocation(models.Model):
    """
    Schema-only representation of a document in the `franchise_locations`
    Mongo collection. Actual reads/writes go through pymongo
    (location_collection), not Django's ORM — Mongo isn't configured as
    a Django DATABASE here. This model exists so ModelSerializer can
    validate against real fields instead of a hand-rolled Serializer.
    Never call .save()/.delete() on instances of this model.
    """
    location_id = models.CharField(max_length=20, unique=True, blank=True)
    Cluster_Name = models.CharField(max_length=200)
    District = models.CharField(max_length=200)
    Covered_Areas = models.CharField(max_length=500, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=50)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=50, blank=True, null=True)
    lastmodified_date = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False  # Django won't create/migrate a table for this
        app_label = 'franchise'

    def __str__(self):
        return f"{self.location_id} - {self.Cluster_Name}"

    def to_mongo_dict(self):
        return {
            "Cluster_Name": self.Cluster_Name,
            "District": self.District,
            "Covered_Areas": self.Covered_Areas,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_date": self.created_date,
            "lastmodified_by": self.lastmodified_by,
            "lastmodified_date": self.lastmodified_date,
            "location_id": self.location_id,
        }