from django.db import models
from django.utils import timezone
from decimal import Decimal
import json
from bson import ObjectId

class MongoJSONField(models.JSONField):
    """
    JSONField that transparently supports native MongoDB BSON lists and dicts
    without crashing or stringifying them when using PyMongo / Djongo.
    """
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value, cls=self.decoder)
            except Exception:
                return value
        return value

    def get_prep_value(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

class Patient(models.Model):
    patient_id = models.CharField(max_length=20, primary_key=True)
    patientname = models.CharField(max_length=220, blank=True, null=True)
    dateOfBirth = models.CharField(max_length=220, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    phoneNumber = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    area = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    franchise_id = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(auto_now=True)

class Billing(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="registrations")
    barcode = models.CharField(max_length=100, unique=True, primary_key=True)
    registrationDate = models.DateTimeField(blank=True, null=True)
    registeredBy = models.CharField(max_length=100, blank=True, null=True)
    referredDoctor = models.CharField(max_length=100, blank=True, null=True)
    trf_file_id = models.CharField(max_length=100, blank=True, null=True)
    testdetails = MongoJSONField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=Decimal('0.00'))
    discountPercentage = models.CharField(max_length=20, blank=True, null=True)
    discountAmount = models.CharField(max_length=20, blank=True, null=True)
    netAmount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=Decimal('0.00'))
    paymentMode = models.CharField(max_length=20, blank=True, null=True)
    payments = MongoJSONField(default=list, blank=True, null=True)
    segment = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")
    remarks = models.TextField(blank=True, null=True, default="")
    franchise_id = models.CharField(max_length=100, blank=True, null=True)
    billing_status = models.CharField(
        max_length=20, 
        choices=[("Pending", "Pending"), ("Billed", "Billed")], 
        default="Pending"
    )
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=Decimal('0.00'))
    due_update_date = models.DateTimeField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reg: {self.patient.patient_id} at {self.registrationDate}"

class RevenueShareModel(models.Model):
    id = models.AutoField(primary_key=True)
    model_name = models.CharField(max_length=100)  # e.g., "Opt1"
    rules = models.JSONField()  # Slab rules like min, max, franchise_share_percentage
    is_active = models.BooleanField(default=True)
    active_from = models.DateField()
    active_till = models.DateField(null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100)
    lastmodified_date = models.DateTimeField(auto_now=True)
    lastmodified_by = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.model_name} - {self.is_active}"

class FranchiseMonthlyRevenue(models.Model):
    id = models.AutoField(primary_key=True)  # global auto ID
    monthly_id = models.CharField(max_length=20, unique=True, editable=False)  
    franchise_id = models.CharField(max_length=100)
    year = models.IntegerField()
    month = models.IntegerField()
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    franchise_share = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    franchiser_share = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    revenue_share_model = models.ForeignKey(RevenueShareModel, on_delete=models.SET_NULL, null=True, blank=True)
    wallet_amount_reduced = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    registrations_refs = models.JSONField(default=list)
    status = models.CharField(
        max_length=10,
        choices=[("active", "Active"), ("closed", "Closed")],
        default="active"
    )
    closed_by = models.CharField(max_length=100, null=True, blank=True)
    closed_date = models.DateTimeField(null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100)
    lastmodified_date = models.DateTimeField(auto_now=True)
    lastmodified_by = models.CharField(max_length=100)

    class Meta:
        unique_together = ['franchise_id', 'year', 'month']

    def save(self, *args, **kwargs):
        # Auto-generate monthly_id if not already set
        if not self.monthly_id:
            self.monthly_id = f"{self.franchise_id}-{self.year}{self.month:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.monthly_id} - ₹{self.total_revenue}"

class Sample(models.Model):
    franchise_id = models.CharField(max_length=100)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    testdetails = models.JSONField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reg: {self.barcode} at {self.created_date}"
    
class Batch(models.Model):
    batch_number = models.CharField(max_length=20, unique=True)
    franchise_id = models.CharField(max_length=100)
    batch_details = models.JSONField(default=list)
    specimen_count = models.JSONField(default=list)
    shipment_from = models.CharField(max_length=100)
    shipment_to = models.CharField(max_length=100)
    received = models.BooleanField(default=False)
    remarks = models.TextField(null=True, blank=True)
    created_by = models.CharField(max_length=100, default="system")
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, default="system")
    lastmodified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.batch_number
    
class TestValue(models.Model):
    date = models.DateField()
    barcode = models.CharField(max_length=100)
    locationId = models.CharField(max_length=100)
    testdetails = models.TextField()

class RefBy(models.Model):
    name = models.CharField(max_length=255)
    qualification = models.CharField(max_length=255, blank=True, null=True)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_date = models.DateTimeField(auto_now=True)
    franchise_id = models.CharField(max_length=100)
    def __str__(self):
        return f"{self.name}"

class PaymentTransaction(models.Model):
    franchise_id = models.CharField(max_length=100)
    barcode = models.CharField(max_length=100) # Link to Billing via barcode
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_mode = models.CharField(max_length=50, blank=True, null=True) # Cash, UPI, etc.
    remarks = models.CharField(max_length=255, blank=True, null=True) # e.g., "Due Clearance", "Initial Payment"
    
    def __str__(self):
        return f"{self.barcode} - {self.amount_paid} on {self.payment_date}"

class SafeJSONField(models.JSONField):
    def db_type(self, connection):
        return 'json'

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        if isinstance(value, (list, dict)):
            return value
        try:
            return super().from_db_value(value, expression, connection)
        except Exception:
            return value

class MaterialRequisition(models.Model):
    mr_number = models.CharField(max_length=50, primary_key=True)
    franchise_id = models.CharField(max_length=100, blank=True, null=True)
    items = SafeJSONField(default=list, blank=True, null=True) # list of {item_id, item_name, quantity, amount}
    Total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=50, default="Draft")
    
    approved_by = models.CharField(max_length=100, blank=True, null=True, default="")
    approved_date = models.DateTimeField(blank=True, null=True)
    
    edited_by = models.CharField(max_length=100, blank=True, null=True, default="")
    edited_reason = models.TextField(blank=True, null=True, default="")
    edited_date = models.DateTimeField(blank=True, null=True)
    
    is_cancelled = models.BooleanField(default=False)
    is_cancelled_by = models.CharField(max_length=100, blank=True, null=True, default="")
    is_cancelled_date = models.DateTimeField(blank=True, null=True)
    
    created_by = models.CharField(max_length=100, default="system")
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, default="system")
    lastmodified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mr_number} - {self.status}"

