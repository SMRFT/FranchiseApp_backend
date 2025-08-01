from django.db import models
from django.utils import timezone


class Patient(models.Model):
    patient_id = models.CharField(max_length=20,primary_key=True)
    patientname = models.CharField(max_length=220,blank=True, null=True)
    dateOfBirth  = models.CharField(max_length=220,blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10,blank=True, null=True)
    phoneNumber = models.CharField(max_length=15,blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    city = models.CharField(max_length=100,blank=True, null=True)
    area = models.CharField(max_length=100,blank=True, null=True)
    pincode = models.CharField(max_length=10,blank=True, null=True)
    franchise_id = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(auto_now_add=True)

    
class Register(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="registrations")
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    registrationDate = models.DateTimeField(blank=True, null=True)
    registeredBy = models.CharField(max_length=100, blank=True, null=True)
    referredDoctor = models.CharField(max_length=100, blank=True, null=True)
    trf_file_id = models.CharField(max_length=100, blank=True, null=True)
    testdetails = models.JSONField(blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount = models.CharField(max_length=20, blank=True, null=True)  # Accepts '10%' or '100'
    netAmount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    paymentMode =models.CharField(max_length=20, blank=True, null=True) 
    segment =models.CharField(max_length=20, blank=True, null=True) 
    franchise_id = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reg: {self.patient.patient_id} at {self.registrationDate}"


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
    


class FranchiseRevenueShare(models.Model):
    min_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2)
    share_percent = models.DecimalField(max_digits=6, decimal_places=2)
    created_date = models.DateTimeField()
    lastmodified_date = models.DateTimeField()

    def __str__(self):
        return f"{self.min_amount}-{self.max_amount}: {self.share_percent}%"
    

class FranchiseMonthlyData(models.Model):
    franchise_id = models.CharField(max_length=100)
    month = models.CharField(max_length=7)  # YYYY-MM
    total_bills = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    franchise_share = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    franchiser_share = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('franchise_id', 'month')


class TestValue(models.Model):
    date = models.DateField()
    barcode = models.CharField(max_length=100)
    locationId = models.CharField(max_length=100)
    testdetails = models.TextField()