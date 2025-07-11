# views.py
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
import gridfs
from bson import ObjectId
from .models import Employee
from .serializers import EmployeeSerializer
import os
from dotenv import load_dotenv
load_dotenv()

# @api_view(['POST'])
# @parser_classes([MultiPartParser])
# def register_employee(request):
#     data = request.data.copy()

#     # Get files from request
#     aadhaar_file = request.FILES.get('aadhaar_proof')
#     payment_file = request.FILES.get('payment_proof')
#     agreement_file = request.FILES.get('agreement_proof')
#     franchise_photo_file = request.FILES.get('franchise_photo')

#     # MongoDB connection
#     mongo_url = os.getenv("MONGO_URL")
#     client = MongoClient(mongo_url)
#     db = client["franchise"]
#     fs = gridfs.GridFS(db)

#     # Store files in GridFS (read the file content first)
#     if aadhaar_file:
#         file_id = fs.put(
#             aadhaar_file.read(), 
#             filename=aadhaar_file.name, 
#             content_type=aadhaar_file.content_type
#         )
#         data['aadhaar_file_id'] = str(file_id)

#     if payment_file:
#         file_id = fs.put(
#             payment_file.read(),
#             filename=payment_file.name,
#             content_type=payment_file.content_type
#         )
#         data['payment_file_id'] = str(file_id)

#     if agreement_file:
#         file_id = fs.put(
#             agreement_file.read(),
#             filename=agreement_file.name,
#             content_type=agreement_file.content_type
#         )
#         data['agreement_file_id'] = str(file_id)

#     if franchise_photo_file:
#         file_id = fs.put(
#             franchise_photo_file.read(),
#             filename=franchise_photo_file.name,
#             content_type=franchise_photo_file.content_type
#         )
#         data['franchise_photo_file_id'] = str(file_id)

#     # Save employee data with file references
#     serializer = EmployeeSerializer(data=data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response({'message': 'Franchise registered successfully'}, status=status.HTTP_201_CREATED)
#     else:
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





from .models import Patient, Register
from .serializers import RegisterSerializer
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from pymongo import MongoClient
import gridfs
import os
import json

from dotenv import load_dotenv
from django.forms.models import model_to_dict
load_dotenv()

@csrf_exempt
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def register_patient(request):
    from .serializers import PatientSerializer
    from .models import Patient
    import os
    import json
    import gridfs
    from bson import ObjectId
    from datetime import datetime
    from django.forms.models import model_to_dict
    from pymongo import MongoClient

    data = request.data.copy()
    trf_file = request.FILES.get("trf")

    # === 1. Check if patient already exists ===
    existing_patient = None
    patientId = data.get("patientId")  # From frontend
    phone = data.get("phoneNumber")

    if patientId:
        existing_patient = Patient.objects.filter(patientId=patientId).first()
    elif phone:
        existing_patient = Patient.objects.filter(phoneNumber=phone).first()

    if existing_patient:
        patient = existing_patient
        patientId = patient.patientId
        patientDetails = model_to_dict(patient)
    else:
        # === 2. Generate New patientId ===
        last_patient = Patient.objects.exclude(patientId=None).order_by('-patientId').first()
        if last_patient and last_patient.patientId:
            import re
            match = re.search(r'SDF(\d+)', last_patient.patientId)
            last_number = int(match.group(1)) if match else 0
        else:
            last_number = 0

        new_number = last_number + 1
        patientId = f"SDF{new_number:03d}"

        # === 3. Create new Patient ===
        patient_data = {
            "patientId": patientId,
            "Patientname": data.get("Patientname"),
            "age": data.get("age"),
            "gender": data.get("gender"),
            "phoneNumber": phone,
            "email": data.get("email"),
            "city": data.get("city"),
            "area": data.get("area"),
            "pincode": data.get("pincode"),
            "dateOfBirth": data.get("dateOfBirth"),
            "created_by": data.get("created_by"),
        }

        patient_serializer = PatientSerializer(data=patient_data)
        if not patient_serializer.is_valid():
            return Response({"error": "Invalid patient data", "details": patient_serializer.errors}, status=400)

        patient = patient_serializer.save()
        patientDetails = model_to_dict(patient)

    # === 4. Parse registrationDate ===
    if "registrationDate" in data:
        try:
            data["registrationDate"] = datetime.strptime(data["registrationDate"], "%Y-%m-%dT%H:%M")
        except ValueError:
            return Response({"error": "Invalid registrationDate format. Use YYYY-MM-DDTHH:MM"}, status=400)

    # === 5. Store TRF file in GridFS ===
    trf_file_id = None
    if trf_file:
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        fs = gridfs.GridFS(db)
        file_id = fs.put(trf_file, filename=trf_file.name, content_type=trf_file.content_type)
        trf_file_id = str(file_id)

    # === 6. Create Register entry ===
    register_data = {
        "patient": patient.pk,
        "patientDetails": patientDetails,
        "registrationDate": data.get("registrationDate"),
        "registeredBy": data.get("registeredBy"),
        "referredDoctor": data.get("referredDoctor"),
        "trf_file_id": trf_file_id,
        "testDetails": json.loads(data.get("testDetails")) if data.get("testDetails") else None,
        "total": data.get("total"),
        "discount": data.get("discount"),
        "netAmount": data.get("netAmount"),
        "paymentMode": data.get("paymentMode"),
        "segment": data.get("segment"),
        "created_by": data.get("created_by")
    }

    serializer = RegisterSerializer(data=register_data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Patient and registration saved successfully",
            "patientId": patientId
        }, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from .models import Patient
from .serializers import PatientSerializer

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from .models import Patient
from .serializers import PatientSerializer

@api_view(['GET'])
def search_patient(request):
    query = request.GET.get("query", "")

    if not query:
        return Response({"error": "Missing query parameter"}, status=400)

    try:
        patient = Patient.objects.filter(
            Q(patientId=query) | Q(phoneNumber=query)
        ).order_by("-created_date").first()

        if patient:
            serializer = PatientSerializer(patient)
            return Response({"patient": serializer.data}, status=200)
        else:
            return Response({"patient": None}, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)



# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from rest_framework import status
# from .models import Patient
# from .serializers import PatientSerializer
# import re

# @api_view(['POST'])
# def patientdetails(request):
#     # Get the last patient with a valid patientId
#     last_patient = Patient.objects.exclude(patientId=None).order_by('-patientId').first()

#     if last_patient and last_patient.patientId:
#         match = re.search(r'SDF(\d+)', last_patient.patientId)
#         if match:
#             last_number = int(match.group(1))
#         else:
#             last_number = 0
#     else:
#         last_number = 0

#     # Increment the number (no fixed digit limit)
#     new_number = last_number + 1

#     # If new_number < 1000, pad to 3 digits, else use full number
#     if new_number < 1000:
#         new_patient_id = f"SDF{new_number:03d}"  # Minimum 3 digits
#     else:
#         new_patient_id = f"SDF{new_number}"      # No padding for big numbers

#     # Copy request and inject patientId
#     patient_data = request.data.copy()
#     patient_data['patientId'] = new_patient_id

#     serializer = PatientSerializer(data=patient_data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response({"message": "Patient saved", "data": serializer.data}, status=status.HTTP_201_CREATED)
#     return Response({"message": "Error", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from django.contrib.auth.hashers import check_password
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

load_dotenv()

# Load environment variables
MONGO_URI = os.getenv('MONGO_URL')
MONGO_DB = os.getenv("MONGO_DB","franchise")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
user_collection = db["franchise_user"]
franchise_collection = db["franchise_franchise"]

@api_view(["POST"])
def login_view(request):
    franchise_id = request.data.get("franchise_id")
    password = request.data.get("password")

    if not franchise_id or not password:
        return Response({"message": "franchise_id and password required"}, status=status.HTTP_400_BAD_REQUEST)

    user = user_collection.find_one({"franchise_id": franchise_id})

    if not user:
        return Response({"message": "Invalid franchise ID"}, status=status.HTTP_404_NOT_FOUND)

    stored_password = user.get("password")
    if check_password(password, stored_password):
        # Fetch extra franchise details
        franchise_data = franchise_collection.find_one({"franchise_id": franchise_id}, {"_id": 0})
        return Response({
            "message": "Login successful",
            "franchise_id": franchise_id,
            "email": user.get("email"),
            "details": franchise_data
        })
    else:
        return Response({"message": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
def get_all_patients(request):
    patients = Patient.objects.all().order_by('-created_date')
    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data)



from datetime import datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Patient
from .serializers import PatientSerializer

from datetime import datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Patient
from .serializers import PatientSerializer

@api_view(['PUT'])
def update_patient(request, pk):
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({"message": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    # Copy request data, but don't include patientId
    update_data = request.data.copy()
    update_data['patientId'] = patient.patientId  # Ensure patientId stays the same

    # Pass data to serializer WITHOUT lastmodified_date
    serializer = PatientSerializer(patient, data=update_data)
    if serializer.is_valid():
        updated_instance = serializer.save()

        # ✅ Update lastmodified_date manually and save again
        updated_instance.lastmodified_date = datetime.now()
        updated_instance.save()

        return Response({"message": "Patient updated", "data": PatientSerializer(updated_instance).data}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)







from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Patient
from .serializers import PatientSerializer

@api_view(['GET'])
def get_patient_by_id(request, patient_id):
    try:
        patient = Patient.objects.get(patientId=patient_id)
        serializer = PatientSerializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Patient.DoesNotExist:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)



from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from .models import Patient
from .serializers import PatientSerializer

@api_view(['GET'])
def patient_list_by_date(request):
    date_str = request.GET.get('date')  # Expecting 'YYYY-MM-DD'

    if date_str:
        try:
            # Parse the start of the day
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            # Get the end of that day (exclusive)
            end_date = start_date + timedelta(days=1)

            patients = Patient.objects.filter(
                created_date__gte=start_date,
                created_date__lt=end_date
            )
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)
    else:
        patients = Patient.objects.all()

    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data)




from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
import os

@api_view(['GET'])
def get_test_details(request):
    try:
        # MongoDB connection
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_testdetails"]

        # Fetch all documents
        test_details = list(collection.find())

        # Convert ObjectId to string for JSON serialization
        for test in test_details:
            test["_id"] = str(test["_id"])

        return Response(test_details, status=200)
    
    except Exception as e:
        return Response({"error": str(e)}, status=500)




from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from datetime import datetime

@api_view(['POST'])
def save_barcode(request):
    barcode = request.data.get("barcode")

    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    collection = db["franchise_preprintedbarcode"]

    collection.insert_one({
        "barcode": barcode,
        "timestamp": datetime.now()
    })

    return Response({"message": "Barcode saved successfully"})
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from decimal import Decimal
import json
from .models import Payment, WalletTransaction, FranchiseWallet

@method_decorator(csrf_exempt, name='dispatch')
class SavePaymentView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Create payment record
            payment = Payment.objects.create(
                reference_id=data['reference_id'],
                payment_id=data.get('payment_id'),
                order_id=data.get('order_id'),
                signature=data.get('signature'),
                amount=Decimal(str(data['amount'])),
                franchise_id=data['franchise_id'],
                franchise_name=data['franchise_name'],
                payment_type=data.get('payment_type', 'razorpay'),
                status=data.get('status', 'success')
            )
            
            # Update wallet balance
            self.update_wallet_balance(
                data['franchise_id'], 
                Decimal(str(data['amount'])), 
                payment
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'Payment saved successfully',
                'payment_id': payment.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': str(e)
            }, status=400)
    
    def update_wallet_balance(self, franchise_id, amount, payment):
        # Get or create wallet
        wallet, created = FranchiseWallet.objects.get_or_create(
            franchise_id=franchise_id,
            defaults={
                'total_balance': 0,
                'franchiser_share': 0,
                'franchise_share': 0
            }
        )
        
        # Calculate shares (60% franchiser, 40% franchise)
        franchiser_amount = amount * Decimal('0.6')
        franchise_amount = amount * Decimal('0.4')
        
        # Update wallet balances
        wallet.total_balance += amount
        wallet.franchiser_share += franchiser_amount
        wallet.franchise_share += franchise_amount
        wallet.save()
        
        # Create wallet transactions
        WalletTransaction.objects.create(
            franchise_id=franchise_id,
            amount=franchiser_amount,
            transaction_type='credit',
            description=f'Franchiser share from payment {payment.reference_id}',
            reference_payment=payment
        )
        
        WalletTransaction.objects.create(
            franchise_id=franchise_id,
            amount=franchise_amount,
            transaction_type='credit',
            description=f'Franchise share from payment {payment.reference_id}',
            reference_payment=payment
        )

@method_decorator(csrf_exempt, name='dispatch')
class AddWalletBalanceView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            franchise_id = data['franchise_id']
            amount = Decimal(str(data['amount']))
            
            # Get or create wallet
            wallet, created = FranchiseWallet.objects.get_or_create(
                franchise_id=franchise_id,
                defaults={
                    'total_balance': 0,
                    'franchiser_share': 0,
                    'franchise_share': 0
                }
            )
            
            # Add to total balance
            wallet.total_balance += amount
            wallet.save()
            
            # Create transaction record
            WalletTransaction.objects.create(
                franchise_id=franchise_id,
                amount=amount,
                transaction_type='credit',
                description='Manual wallet balance addition'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Wallet balance added successfully',
                'new_balance': float(wallet.total_balance)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

class WalletBalanceView(View):
    def get(self, request, franchise_id):
        try:
            wallet, created = FranchiseWallet.objects.get_or_create(
                franchise_id=franchise_id,
                defaults={
                    'total_balance': 0,
                    'franchiser_share': 0,
                    'franchise_share': 0
                }
            )
            
            return JsonResponse({
                'total_balance': float(wallet.total_balance),
                'franchiser_share': float(wallet.franchiser_share),
                'franchise_share': float(wallet.franchise_share)
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)

class PaymentHistoryView(View):
    def get(self, request, franchise_id):
        try:
            payments = Payment.objects.filter(
                franchise_id=franchise_id
            ).order_by('-created_at')[:20]  # Last 20 payments
            
            payment_data = []
            for payment in payments:
                payment_data.append({
                    'reference_id': payment.reference_id,
                    'payment_id': payment.payment_id,
                    'amount': float(payment.amount),
                    'status': payment.status,
                    'payment_type': payment.payment_type,
                    'created_at': payment.created_at.isoformat()
                })
            
            return JsonResponse({
                'payments': payment_data
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
