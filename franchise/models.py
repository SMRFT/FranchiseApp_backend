from django.db import models

# Create your models here.
from django.db import models

class Employee(models.Model):
    franchise_id = models.CharField(max_length=100)
    franchiser_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=15)
    email = models.EmailField()
    alt_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField()
    qualification = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    pincode = models.CharField(max_length=10)
    dob = models.DateField(null=True, blank=True)


    #files id 
    aadhaar_file_id = models.CharField(max_length=100, blank=True, null=True)
    payment_file_id = models.CharField(max_length=100, blank=True, null=True)
    agreement_file_id = models.CharField(max_length=100, blank=True, null=True)
    franchise_photo_file_id = models.CharField(max_length=100, blank=True, null=True)

    


    def __str__(self):
        return self.franchiser_name


from django.db import models

class Patient(models.Model):
    patientId = models.CharField(max_length=20,primary_key=True)
    Patientname = models.CharField(max_length=220,blank=True, null=True)
    dateOfBirth  = models.CharField(max_length=220,blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10,blank=True, null=True)
    phoneNumber = models.CharField(max_length=15,blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    city = models.CharField(max_length=100,blank=True, null=True)
    area = models.CharField(max_length=100,blank=True, null=True)
    pincode = models.CharField(max_length=10,blank=True, null=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(auto_now_add=True)

    
class Register(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="registrations")
    patientDetails = models.JSONField(blank=True, null=True) 
    registrationDate = models.DateTimeField(blank=True, null=True)
    registeredBy = models.CharField(max_length=100, blank=True, null=True)
    referredDoctor = models.CharField(max_length=100, blank=True, null=True)
    trf_file_id = models.CharField(max_length=100, blank=True, null=True)
    testDetails = models.JSONField(blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount = models.CharField(max_length=20, blank=True, null=True)  # Accepts '10%' or '100'
    netAmount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    paymentMode =models.CharField(max_length=20, blank=True, null=True) 
    segment =models.CharField(max_length=20, blank=True, null=True) 
    created_by = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reg: {self.patient.patientId} at {self.registrationDate}"
    


class Payment(models.Model):
    reference_id = models.CharField(max_length=100, unique=True)
    payment_id = models.CharField(max_length=100, null=True, blank=True)
    order_id = models.CharField(max_length=100, null=True, blank=True)
    signature = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    franchise_id = models.CharField(max_length=50)
    franchise_name = models.CharField(max_length=200)
    payment_type = models.CharField(max_length=20, default='razorpay')
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class WalletTransaction(models.Model):
    franchise_id = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10)  # credit, debit
    description = models.TextField(null=True, blank=True)
    reference_payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



class FranchiseWallet(models.Model):
    franchise_id = models.CharField(max_length=50, unique=True)
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    franchiser_share = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    franchise_share = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)


