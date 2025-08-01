# views.py
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework import status
from django.http import HttpResponse
from bson.json_util import dumps
from pymongo import MongoClient
import os
from datetime import datetime, date
from django.utils import timezone
import json
import re
from datetime import datetime, timedelta
from .models import Patient
from .serializers import PatientSerializer
import gridfs
from bson import ObjectId
from .models import Patient, Register
from .serializers import RegisterSerializer
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.dateparse import parse_date
from django.forms.models import model_to_dict
from django.db.models import Q
from dotenv import load_dotenv
from django.contrib.auth.hashers import check_password
from collections import Counter

load_dotenv()

@csrf_exempt
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def register_patient(request):
    data = request.data.copy()
    trf_file = request.FILES.get("trf")
    barcode_id = data.get("barcodeId")
    existing_patient = None
    patient_id = data.get("patient_id")
    phone = data.get("phoneNumber")
    
    # === ALWAYS GENERATE UNIQUE PATIENT ID FOR EACH REGISTRATION ===
    def generate_unique_patient_id():
        last_patient = Patient.objects.exclude(patient_id=None).order_by('-patient_id').first()
        if last_patient and last_patient.patient_id:
            match = re.search(r'SDF(\d+)', last_patient.patient_id)
            last_number = int(match.group(1)) if match else 0
        else:
            last_number = 0
        new_number = last_number + 1
        return f"SDF{new_number:03d}"
    
    # Generate unique patient ID for this registration
    unique_patient_id = generate_unique_patient_id()
    
    # Check if patient exists (for getting patient details)
    if patient_id:
        existing_patient = Patient.objects.filter(patient_id=patient_id).first()
    elif phone:
        existing_patient = Patient.objects.filter(phoneNumber=phone).first()
    
    if existing_patient:
        # Use existing patient details but with NEW unique patient ID
        patient = existing_patient
        patientDetails = model_to_dict(patient)
        # Override with new unique patient ID
        patientDetails['patient_id'] = unique_patient_id
        
        # Create new patient record with unique ID
        patient_data = {
            "patient_id": unique_patient_id,
            "patientname": patientDetails.get("patientname"),
            "age": patientDetails.get("age"),
            "gender": patientDetails.get("gender"),
            "phoneNumber": patientDetails.get("phoneNumber"),
            "email": patientDetails.get("email"),
            "city": patientDetails.get("city"),
            "area": patientDetails.get("area"),
            "pincode": patientDetails.get("pincode"),
            "dateOfBirth": patientDetails.get("dateOfBirth"),
            "franchise_id": data.get("franchise_id"),
        }
        patient_serializer = PatientSerializer(data=patient_data)
        if not patient_serializer.is_valid():
            return Response({"error": "Invalid patient data", "details": patient_serializer.errors}, status=400)
        patient = patient_serializer.save()
        patientDetails = model_to_dict(patient)
    else:
        # Create completely new patient with unique ID
        patient_data = {
            "patient_id": unique_patient_id,
            "patientname": data.get("patientname"),
            "age": data.get("age"),
            "gender": data.get("gender"),
            "phoneNumber": phone,
            "email": data.get("email"),
            "city": data.get("city"),
            "area": data.get("area"),
            "pincode": data.get("pincode"),
            "dateOfBirth": data.get("dateOfBirth"),
            "franchise_id": data.get("franchise_id"),
        }
        patient_serializer = PatientSerializer(data=patient_data)
        if not patient_serializer.is_valid():
            return Response({"error": "Invalid patient data", "details": patient_serializer.errors}, status=400)
        patient = patient_serializer.save()
        patientDetails = model_to_dict(patient)
    
    # === 3. Parse registrationDate ===
    if "registrationDate" in data:
        try:
            data["registrationDate"] = datetime.strptime(data["registrationDate"], "%Y-%m-%dT%H:%M")
        except ValueError:
            return Response({"error": "Invalid registrationDate format. Use YYYY-MM-DDTHH:MM"}, status=400)
    
    # === 4. Store TRF in GridFS ===
    trf_file_id = None
    if trf_file:
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        fs = gridfs.GridFS(db)
        file_id = fs.put(trf_file, filename=trf_file.name, content_type=trf_file.content_type)
        trf_file_id = str(file_id)
    
    # === 5. Save Registration ===
    register_data = {
        "patient": patient.pk,
        "registrationDate": data.get("registrationDate"),
        "referredDoctor": data.get("referredDoctor"),
        "trf_file_id": trf_file_id,
        "testdetails": json.loads(data.get("testdetails")) if data.get("testdetails") else None,
        "total": data.get("total"),
        "discount": data.get("discount"),
        "netAmount": data.get("netAmount"),
        "paymentMode": data.get("paymentMode"),
        "segment": data.get("segment"),
        "barcode": barcode_id,
        "franchise_id": data.get("franchise_id")
    }
    
    serializer = RegisterSerializer(data=register_data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Patient and registration saved successfully",
            "patient_id": unique_patient_id  # Return the new unique patient ID
        }, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
def search_patient(request):
    query = request.GET.get("query", "")

    if not query:
        return Response({"error": "Missing query parameter"}, status=400)

    try:
        patient = Patient.objects.filter(
            Q(patient_id=query) | Q(phoneNumber=query)
        ).order_by("-created_date").first()

        if patient:
            serializer = PatientSerializer(patient)
            return Response({"patient": serializer.data}, status=200)
        else:
            return Response({"patient": None}, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)



mongo_url = os.getenv("GLOBAL_DB_HOST")
client = MongoClient(mongo_url)
db = client["franchise"]
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
    # :white_check_mark: Check is_active from franchise_collection
    franchise_data = franchise_collection.find_one({"franchise_id": franchise_id})
    if not franchise_data:
        return Response({"message": "Franchise data not found"}, status=status.HTTP_404_NOT_FOUND)
    if not franchise_data.get("is_active", False):
        return Response({"message": "Franchise is inactive. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
    stored_password = user.get("password")
    if check_password(password, stored_password):
        # :white_check_mark: Extract franchiser name if available
        franchise_name = franchise_data.get("franchise_name", "Unknown Franchise")
        return Response({
            "message": "Login successful",
            "franchise_id": franchise_id,
            "email": user.get("email"),
            "name": franchise_name,
        })
    else:
        return Response({"message": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

    

@api_view(['GET'])
def get_all_patients(request):
    franchise_id = request.GET.get('franchise_id')
    if franchise_id:
        patients = Patient.objects.filter(franchise_id=franchise_id).order_by('-created_date')
    else:
        patients = Patient.objects.all().order_by('-created_date')

    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime, timedelta
from .models import Register, Patient
from .serializers import RegisterSerializer, PatientSerializer
from bson.objectid import ObjectId  # If needed

@api_view(["GET"])
def get_registrations_by_franchise_and_date(request):
    franchise_id = request.GET.get("franchise_id")
    date_str = request.GET.get("date")  # format: YYYY-MM-DD

    if not franchise_id or not date_str:
        return Response({"error": "franchise_id and date are required"}, status=400)

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        start_datetime = datetime.combine(date, datetime.min.time())
        end_datetime = datetime.combine(date, datetime.max.time())
    except Exception:
        return Response({"error": "Invalid date format"}, status=400)

    # Filter registrations for that franchise on that day
    registrations = Register.objects.filter(
        franchise_id=franchise_id,
        registrationDate__gte=start_datetime,
        registrationDate__lt=end_datetime
    ).order_by("-registrationDate")

    results = []
    for reg in registrations:
        # Fetch related patient data using patient_id
        try:
            patient = Patient.objects.get(patient_id=reg.patient_id)
            patient_data = {
                "patientname": patient.patientname,
                "phoneNumber": patient.phoneNumber,
                "email": patient.email,
                "city": patient.city,
                "area": patient.area,
            }
        except Patient.DoesNotExist:
            patient_data = {}

        reg_data = RegisterSerializer(reg).data
        reg_data["patient_info"] = patient_data
        results.append(reg_data)

    return Response(results)



@api_view(['PUT'])
def update_patient(request, pk):
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({"message": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    # Copy request data, but don't include patient_id
    update_data = request.data.copy()
    update_data['patient_id'] = patient.patient_id  # Ensure patient_id stays the same

    # Pass data to serializer WITHOUT lastmodified_date
    serializer = PatientSerializer(patient, data=update_data)
    if serializer.is_valid():
        updated_instance = serializer.save()

        # ✅ Update lastmodified_date manually and save again
        updated_instance.lastmodified_date = datetime.now()
        updated_instance.save()

        return Response({"message": "Patient updated", "data": PatientSerializer(updated_instance).data}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_patient_by_id(request, patient_id):
    try:
        patient = Patient.objects.get(patient_id=patient_id)
        serializer = PatientSerializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Patient.DoesNotExist:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)


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


@api_view(['GET'])
def get_test_details(request):
    try:
        # MongoDB connection
        mongo_url = os.getenv("GLOBAL_DB_HOST")
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


@api_view(['GET'])
def get_active_franchise_locations(request):
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_location_details"]

        # Only fetch documents where is_active is true
        data = list(collection.find({ "is_active": True }))

        json_data = dumps(data, indent=2)  # Converts ObjectId and datetime properly

        return HttpResponse(json_data, content_type="application/json")

    except Exception as e:
        return HttpResponse(dumps({ "error": str(e) }), content_type="application/json", status=500)
    

@api_view(['PATCH'])
def update_barcode_status(request, barcode_id):
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_barcoderange"]

        # Parse request body
        new_status = request.data.get("is_active")
        if new_status is None:
            return Response({"error": "Missing 'is_active' field"}, status=400)

        # Update the is_active field
        result = collection.update_one(
            {"_id": ObjectId(barcode_id)},
            {"$set": {"is_active": new_status}}
        )

        if result.matched_count == 0:
            return Response({"error": "Document not found"}, status=404)

        return Response({"message": "Status updated successfully"})

    except Exception as e:
        return Response({"error": str(e)}, status=500)


from .models import Register, Sample # Assuming these are Django models or Mongoengine documents
# Helper to parse date string
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()




from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from django.conf import settings
from .models import Register
import os

@api_view(['GET'])
def check_barcode_exists(request):
    barcode_id = request.GET.get("barcodeId")

    if not barcode_id:
        return Response({"error": "barcodeId is required."}, status=400)

    # 1. Check if barcode already registered in Register model
    if Register.objects.filter(barcode=barcode_id).exists():
        return Response({"exists": True, "valid": False, "message": "This barcode is already used."}, status=200)

    # 2. Connect to MongoDB
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]

    # 3. Check if barcode is already registered in franchise_register collection
    franchise_register = db["franchise_register"]
    if franchise_register.find_one({"barcode": barcode_id}):
        return Response({"exists": True, "valid": False, "message": "This barcode is already registered in franchise_register."}, status=200)

    # 4. Check all franchise_barcodestock ranges
    barcode_stock = db["franchise_barcodestock"]
    try:
        barcode_int = int(barcode_id)
    except ValueError:
        return Response({"exists": False, "valid": False, "message": "Invalid barcode format (should be numeric)."}, status=200)

    matching_range = barcode_stock.find_one({
        "$expr": {
            "$and": [
                {"$lte": [{"$toInt": "$startbarcode"}, barcode_int]},
                {"$gte": [{"$toInt": "$endbarcode"}, barcode_int]}
            ]
        }
    })

    if matching_range:
        return Response({"exists": False, "valid": True, "message": "Barcode is valid and within allowed range."}, status=200)
    else:
        return Response({"exists": False, "valid": False, "message": "Barcode is not in any registered stock range."}, status=200)







from .models import Register, Sample # Assuming these are Django models or Mongoengine documents
# Helper to parse date string
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()

@csrf_exempt
@api_view(['GET'])
def get_patient_by_franchise_and_date(request):
    franchise_id = request.GET.get('franchise_id')
    date_str = request.GET.get('date')

    if not franchise_id or not date_str:
        return JsonResponse({'error': 'Missing franchise_id or date'}, status=400)

    try:
        target_date = parse_date(date_str)
        next_day = target_date + timedelta(days=1)

        # Fetch registrations for the given date and franchise
        registrations = Register.objects.filter(
            franchise_id=franchise_id,
            registrationDate__gte=target_date,
            registrationDate__lt=next_day
        ).select_related('patient')

        result = []
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        sample_collection = db["franchise_sample"]

        for reg in registrations:
            barcode = reg.barcode
           
            # Check if a Sample document exists for this patient and franchise
            sample_doc = sample_collection.find_one({
                "franchise_id": franchise_id,
                "barcode": barcode
            })

            should_display_patient = False
            if sample_doc is None:
                # No sample record yet, so all tests are pending. Display the patient.
                should_display_patient = True
            else:
                # Sample record exists, check its testdetails statuses
                sample_testdetails_str = sample_doc.get('testdetails', '[]')
                sample_testdetails = []
                if isinstance(sample_testdetails_str, str):
                    try:
                        sample_testdetails = json.loads(sample_testdetails_str)
                    except json.JSONDecodeError:
                        sample_testdetails = [] # Fallback if parsing fails
                elif isinstance(sample_testdetails_str, list): # Handle if it's already a list (e.g., from old data)
                    sample_testdetails = sample_testdetails_str
               
                # Check if any test is still 'Pending'
                if any(test.get('samplestatus') == 'Pending' for test in sample_testdetails if isinstance(test, dict)):
                    should_display_patient = True
                # If all are 'Collected', should_display_patient remains False

            if should_display_patient:
                result.append({
                    'barcode': reg.barcode,
                    'patient_id': reg.patient.patient_id if reg.patient else None,
                    'patientname': reg.patient.patientname if reg.patient else None,
                    'franchise_id': reg.franchise_id,
                    'registrationDate': reg.registrationDate.isoformat() if reg.registrationDate else None,
                    'barcode': reg.barcode,
                    'testdetails': reg.testdetails, # This is the original test details from Register
                })
        return JsonResponse(result, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET', 'POST', 'PATCH'])
def sample(request):
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    sample_collection = db["franchise_sample"]
    register_collection = db["franchise_register"]

    if request.method == 'POST':
        franchise_id = request.data.get('franchise_id')
        barcode = request.data.get('barcode')
        incoming_testdetails = request.data.get('testdetails', [])

        if not isinstance(incoming_testdetails, list):
            return Response({"error": "testdetails must be a list of objects"}, status=status.HTTP_400_BAD_REQUEST)

        # :wrench: FIX: Now checking both franchise_id and barcode
        existing_sample = sample_collection.find_one({
            "franchise_id": franchise_id,
            "barcode": barcode
        })

        if existing_sample:
            # Update existing sample document
            existing_testdetails_str = existing_sample.get('testdetails', '[]')
            existing_testdetails = []
            if isinstance(existing_testdetails_str, str):
                try:
                    existing_testdetails = json.loads(existing_testdetails_str)
                except json.JSONDecodeError:
                    existing_testdetails = []
            elif isinstance(existing_testdetails_str, list):
                existing_testdetails = existing_testdetails_str

            # :wrench: FIXED: Use test_id as the unique key instead of (testname, container)
            incoming_updates_map = {}
            for test_item in incoming_testdetails:
                if isinstance(test_item, dict):
                    test_id = test_item.get('test_id')
                    if test_id:
                        incoming_updates_map[test_id] = test_item

            final_testdetails_list = []
            # Update existing tests based on test_id
            for existing_test in existing_testdetails:
                if isinstance(existing_test, dict):
                    test_id = existing_test.get('test_id')
                    if test_id and test_id in incoming_updates_map:
                        updated_test_data = incoming_updates_map[test_id]
                        existing_test['samplestatus'] = updated_test_data.get('samplestatus', existing_test.get('samplestatus'))
                        existing_test['samplecollected_time'] = updated_test_data.get('samplecollected_time', existing_test.get('samplecollected_time'))

                        # Set collected_by on existing_test
                        if updated_test_data.get('samplestatus') == 'Collected' and franchise_id:
                            existing_test['collected_by'] = franchise_id

                        final_testdetails_list.append(existing_test)
                        del incoming_updates_map[test_id]
                    else:
                        final_testdetails_list.append(existing_test)
           
            # Add any new tests that were not in existing_testdetails
            for test_id, new_test_data in incoming_updates_map.items():
                if new_test_data.get('samplestatus') == 'Collected':
                    new_test_data['collected_by'] = franchise_id
                else:
                    new_test_data['collected_by'] = None
                final_testdetails_list.append(new_test_data)

            final_testdetails_json_str = json.dumps(final_testdetails_list)

            update_fields = {
                "testdetails": final_testdetails_json_str,
                "lastmodified_by": franchise_id,
                "lastmodified_date": datetime.now()
            }
           
            result = sample_collection.update_one(
                {"_id": existing_sample["_id"]},
                {"$set": update_fields}
            )
            if result.modified_count == 1:
                return Response({"message": "Sample updated successfully."}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No changes detected, sample not modified."}, status=status.HTTP_200_OK)
       
        else:
            # Create new sample document
            new_sample_doc = {
                "franchise_id": franchise_id,
                "barcode": barcode,
                "testdetails": [],
                "created_date": datetime.now(),
                "lastmodified_by": franchise_id,
                "lastmodified_date": datetime.now()
            }
           
            # Populate testdetails for the new document
            for test_item in incoming_testdetails:
                if isinstance(test_item, dict):
                    if test_item.get('samplestatus') == 'Collected':
                        test_item['collected_by'] = franchise_id
                    else:
                        test_item['collected_by'] = None
                    new_sample_doc['testdetails'].append(test_item)
           
            new_sample_doc['testdetails'] = json.dumps(new_sample_doc['testdetails'])

            insert_result = sample_collection.insert_one(new_sample_doc)
            if insert_result.inserted_id:
                return Response({"message": "Sample created successfully.", "id": str(insert_result.inserted_id)}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": "Failed to create sample."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'GET':
        barcode = request.GET.get('barcode')
        franchise_id = request.GET.get('franchise_id')
        date_str = request.GET.get('date')  # For filtering collected samples

        if barcode and franchise_id:
            sample_doc = sample_collection.find_one({
                "franchise_id": franchise_id,
                "barcode": barcode
            })

            if sample_doc:
                # :mag: Get patient_id from Register model using barcode
                register_doc = register_collection.find_one({"barcode": barcode})
                sample_doc['patient_id'] = register_doc.get('patient_id') if register_doc else None

                # Parse testdetails
                testdetails = sample_doc.get('testdetails', [])
                if isinstance(testdetails, str):
                    try:
                        testdetails = json.loads(testdetails)
                    except json.JSONDecodeError:
                        testdetails = []
                elif not isinstance(testdetails, list):
                    testdetails = [testdetails]

                sample_doc['testdetails'] = testdetails
                sample_doc['_id'] = str(sample_doc['_id'])

                return Response(sample_doc, status=200)
            else:
                return Response({"message": "No sample data found for this patient."}, status=404)

        elif franchise_id and date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d")
                next_day = target_date + timedelta(days=1)

                all_samples = sample_collection.find({
                    "franchise_id": franchise_id,
                    "created_date": {"$gte": target_date, "$lt": next_day}
                })

                result_samples = []
                for sample_doc in all_samples:
                    testdetails_raw = sample_doc.get('testdetails', [])
                    if isinstance(testdetails_raw, str):
                        try:
                            testdetails = json.loads(testdetails_raw)
                        except json.JSONDecodeError:
                            testdetails = []
                    elif isinstance(testdetails_raw, list):
                        testdetails = testdetails_raw
                    else:
                        testdetails = []

                    # :white_check_mark: Filter only 'Collected' testdetails
                    collected_tests = [
                        test for test in testdetails
                        if isinstance(test, dict) and test.get('samplestatus') == 'Collected'
                    ]

                    if collected_tests:
                        sample_doc['_id'] = str(sample_doc['_id'])
                        sample_doc['testdetails'] = collected_tests

                        # :mag: Attach patient_id from Register model using barcode
                        register_doc = register_collection.find_one({"barcode": sample_doc.get("barcode")})
                        sample_doc["patient_id"] = register_doc.get("patient_id") if register_doc else None

                        result_samples.append(sample_doc)

                return Response(result_samples, status=200)
            except Exception as e:
                return Response({'error': str(e)}, status=500)

        else:
            return Response({"error": "Missing barcode/franchise_id or franchise_id/date for GET."}, status=400)

    elif request.method == 'PATCH':
        franchise_id = request.data.get('franchise_id')
        barcode = request.data.get('barcode')
        incoming_testdetails = request.data.get('testdetails', [])

        if not franchise_id or not barcode or not isinstance(incoming_testdetails, list):
            return Response({"error": "franchise_id, barcode, and testdetails (list) are required for PATCH."}, status=400)

        existing_sample = sample_collection.find_one({
            "franchise_id": franchise_id,
            "barcode": barcode
        })

        if not existing_sample:
            return Response({"error": "Sample not found in MongoDB."}, status=404)

        # Parse existing testdetails from JSON string
        existing_testdetails_str = existing_sample.get('testdetails', '[]')
        existing_testdetails_list = []
        if isinstance(existing_testdetails_str, str):
            try:
                existing_testdetails_list = json.loads(existing_testdetails_str)
            except json.JSONDecodeError:
                existing_testdetails_list = []
        elif isinstance(existing_testdetails_str, list):
            existing_testdetails_list = existing_testdetails_str

        # :wrench: FIXED: Use test_id as the unique key for updates
        incoming_updates_map = {}
        for test_item in incoming_testdetails:
            if isinstance(test_item, dict):
                test_id = test_item.get('test_id')
                if test_id:
                    incoming_updates_map[test_id] = test_item

        # Update existing tests based on test_id
        updated_testdetails_list = []
        for existing_test in existing_testdetails_list:
            if isinstance(existing_test, dict):
                test_id = existing_test.get('test_id')
                if test_id and test_id in incoming_updates_map:
                    updated_test_data = incoming_updates_map[test_id]
                    new_status = updated_test_data.get('samplestatus', existing_test.get('samplestatus'))

                    existing_test['samplestatus'] = new_status

                    if new_status == 'Transferred':
                        existing_test['transferred_by'] = franchise_id
                        existing_test['sampletransferred_time'] = updated_test_data.get(
                            'sampletransferred_time',
                            datetime.now().isoformat()
                        )
                    else:
                        existing_test['transferred_by'] = existing_test.get('transferred_by')
                        existing_test['sampletransferred_time'] = existing_test.get('sampletransferred_time')

                    # Preserve collected_by and samplecollected_time if not already present
                    if 'collected_by' not in existing_test and 'collected_by' in updated_test_data:
                        existing_test['collected_by'] = updated_test_data['collected_by']
                    if 'samplecollected_time' not in existing_test and 'samplecollected_time' in updated_test_data:
                        existing_test['samplecollected_time'] = updated_test_data['samplecollected_time']

                    updated_testdetails_list.append(existing_test)
                    del incoming_updates_map[test_id]
                else:
                    updated_testdetails_list.append(existing_test)
            else:
                updated_testdetails_list.append(existing_test)

        # Add any new tests
        for test_id, new_test_data in incoming_updates_map.items():
            new_status = new_test_data.get('samplestatus')
            if new_status == 'Transferred':
                new_test_data['transferred_by'] = franchise_id
                new_test_data['sampletransferred_time'] = datetime.now().isoformat()
            else:
                new_test_data['transferred_by'] = new_test_data.get('transferred_by')
                new_test_data['sampletransferred_time'] = new_test_data.get('sampletransferred_time')
            updated_testdetails_list.append(new_test_data)

        final_testdetails_json_str = json.dumps(updated_testdetails_list)

        update_fields = {
            "testdetails": final_testdetails_json_str,
            "lastmodified_by": franchise_id,
            "lastmodified_date": datetime.now()
        }

        result = sample_collection.update_one(
            {"_id": existing_sample["_id"]},
            {"$set": update_fields}
        )
        if result.modified_count == 1:
            return Response({"message": "Sample updated successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "No changes detected, sample not modified."}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_transferred_samples(request):
    franchise_id = request.GET.get('franchise_id')
    samplestatus = request.GET.get('samplestatus', 'Transferred')
    date_param = request.GET.get('date')

    if not franchise_id:
        return Response({'error': 'franchise_id is required'}, status=400)

    try:
        records = Sample.objects.filter(franchise_id=franchise_id)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

    matched_samples = []

    # Optional date filtering
    if date_param:
        try:
            filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()

            if timezone.is_aware(timezone.now()):
                start_date = timezone.make_aware(datetime.combine(filter_date, datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(filter_date, datetime.max.time()))
                records = records.filter(created_date__range=[start_date, end_date])
            else:
                records = records.filter(created_date__date=filter_date)
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    for record in records:
        try:
            testdetails = record.testdetails

            # Parse testdetails if stored as a JSON string
            if isinstance(testdetails, str):
                try:
                    testdetails = json.loads(testdetails)
                except json.JSONDecodeError:
                    # Attempt to fix invalid JSON
                    fixed_json = re.sub(r'(\w+):', r'"\1":', testdetails)
                    fixed_json = re.sub(r':\s*([A-Za-z][^",\[\]{}]*?)(?=,|\})', r': "\1"', fixed_json)
                    fixed_json = re.sub(r':\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)', r': "\1"', fixed_json)
                    fixed_json = re.sub(r'""([^"]*?)""', r'"\1"', fixed_json)
                    try:
                        testdetails = json.loads(fixed_json)
                    except json.JSONDecodeError:
                        continue

            if not isinstance(testdetails, list):
                testdetails = [testdetails]

            # Check for samplestatus and batch_number is null
            for test in testdetails:
                if (
                    isinstance(test, dict) and
                    test.get('samplestatus') == samplestatus and
                    test.get('batch_number') in [None, '', 'null']
                ):
                    matched_samples.append({
                        'franchise_id': record.franchise_id,
                        'barcode': record.barcode,
                        'testdetails': test
                    })

        except Exception as e:
            print(f"Error processing record {record.franchise_id}: {str(e)}")
            continue

    return Response({'transferred_samples': matched_samples})
     

from .models import Batch
from .serializers import BatchSerializer
@api_view(['POST', 'GET'])
def batch_generation(request):
    if request.method == 'GET':
        try:
            batches = Batch.objects.all().order_by('-created_date')
            serializer = BatchSerializer(batches, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'POST':
        try:
            # Connect to MongoDB
            mongo_url = os.getenv("GLOBAL_DB_HOST")
            client = MongoClient(mongo_url)
            db = client["franchise"]
            sample_collection = db['franchise_sample']
            testdetails_collection = db['franchise_testdetails']
            franchise_collection = db['franchise_franchise']
            franchise_location_details = db['franchise_location_details']

            # 1. Generate next batch number
            last_batch = Batch.objects.exclude(batch_number=None).order_by('-created_date').first()
            if last_batch and last_batch.batch_number and last_batch.batch_number.isdigit():
                next_number = str(int(last_batch.batch_number) + 1).zfill(5)
            else:
                next_number = "00001"

            data = dict(request.data)
            data['batch_number'] = next_number

            # 2. Parse and deduplicate batch_details
            raw_batch_details = request.data.get("batch_details", [])
            if isinstance(raw_batch_details, str):
                try:
                    raw_batch_details = json.loads(raw_batch_details)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid JSON in batch_details"}, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(raw_batch_details, list):
                return Response({"error": "batch_details must be a list"}, status=status.HTTP_400_BAD_REQUEST)

            seen_barcodes = set()
            unique_batch_list = []
            for item in raw_batch_details:
                if isinstance(item, dict):
                    barcode = item.get("barcode")
                    if barcode and barcode not in seen_barcodes:
                        seen_barcodes.add(barcode)
                        unique_batch_list.append({"barcode": barcode})
            data["batch_details"] = unique_batch_list

            # 3. :wrench: IMPROVED: Collect specimen types using test_id for accurate matching
            franchise_id = data.get('franchise_id')
            specimen_counter = Counter()
           
            if franchise_id:
                batch_barcodes = [item["barcode"] for item in unique_batch_list]
                sample_records = sample_collection.find({
                    "franchise_id": franchise_id,
                    "barcode": {"$in": batch_barcodes}
                })
               
                for record in sample_records:
                    testdetails_raw = record.get("testdetails")
                    if not testdetails_raw:
                        continue

                    testdetails = []
                    try:
                        if isinstance(testdetails_raw, list):
                            testdetails = testdetails_raw
                        elif isinstance(testdetails_raw, str):
                            try:
                                testdetails = json.loads(testdetails_raw)
                            except json.JSONDecodeError:
                                fixed_json = re.sub(r'([{,])(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\2"\3":', testdetails_raw)
                                testdetails = json.loads(fixed_json)
                        elif isinstance(testdetails_raw, dict):
                            testdetails = [testdetails_raw]
                    except Exception as e:
                        print(f"Error parsing testdetails for barcode {record.get('barcode')}: {str(e)}")
                        continue

                    for test in testdetails:
                        if isinstance(test, dict):
                            test_id = test.get("test_id")
                            if test_id:
                                test_obj = testdetails_collection.find_one({"test_id": test_id})
                                if test_obj:
                                    specimen_type = test_obj.get("specimen_type")
                                    if specimen_type:
                                        specimen_counter[specimen_type] += 1
                            else:
                                testname = test.get("testname")
                                if testname:
                                    test_obj = testdetails_collection.find_one({"test_name": testname})
                                    if test_obj:
                                        specimen_type = test_obj.get("specimen_type")
                                        if specimen_type:
                                            specimen_counter[specimen_type] += 1

            data["specimen_count"] = [
                {"specimen_type": specimen_type, "count": count}
                for specimen_type, count in specimen_counter.items()
            ]

            # 4. Get shipment_from from franchise_id -> location_id -> Cluster_Name
            shipment_from_franchise_id = data.get('franchise_id')

            if shipment_from_franchise_id:
                franchise_obj = franchise_collection.find_one({"franchise_id": shipment_from_franchise_id})
                if not franchise_obj:
                    return Response(
                        {"error": f"Invalid shipment_from: franchise_id '{shipment_from_franchise_id}' not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                location_id = franchise_obj.get("location_id")
                if not location_id:
                    return Response(
                        {"error": f"No location_id found for franchise_id '{shipment_from_franchise_id}'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                location_obj = franchise_location_details.find_one({"location_id": location_id})
                if not location_obj or not location_obj.get("Cluster_Name"):
                    return Response(
                        {"error": f"No Cluster_Name found for location_id '{location_id}'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                data["shipment_from"] = location_obj["Cluster_Name"]
            else:
                return Response(
                    {"error": "shipment_from (franchise_id) is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            data["shipment_to"] = "Shanmuga Reference Lab"

            # 5. Save to database
            serializer = BatchSerializer(data=data)
            if serializer.is_valid():
                batch_instance = serializer.save()
               
                print(f"Batch {next_number} created successfully with {len(unique_batch_list)} samples")
                print(f"Specimen count breakdown: {data['specimen_count']}")

                # 6. :white_check_mark: Update batch_number for only Transferred tests in sample_collection
                for item in unique_batch_list:
                    barcode = item.get("barcode")
                    if not barcode:
                        continue

                    sample_doc = sample_collection.find_one({
                        "barcode": barcode,
                        "franchise_id": franchise_id
                    })

                    if sample_doc:
                        testdetails_raw = sample_doc.get("testdetails")
                        try:
                            # Always parse from string
                            if isinstance(testdetails_raw, str):
                                testdetails = json.loads(testdetails_raw)
                            elif isinstance(testdetails_raw, list):
                                testdetails = testdetails_raw
                            else:
                                continue
                        except Exception as e:
                            print(f"Failed to parse testdetails for barcode {barcode}: {e}")
                            continue

                        updated = False
                        for test in testdetails:
                            if (
                                isinstance(test, dict) and
                                test.get("samplestatus") == "Transferred" and
                                test.get("batch_number") in [None, '', 'null']
                            ):
                                test["batch_number"] = next_number
                                updated = True

                        if updated:
                            # Re-serialize testdetails back to string before updating MongoDB
                            sample_collection.update_one(
                                {"_id": sample_doc["_id"]},
                                {"$set": {"testdetails": json.dumps(testdetails)}}
                            )

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import requests
from .models import TestValue
from .serializers import TestValueSerializer
@api_view(['GET'])
def get_test_values(request):
    location_id = request.GET.get('locationId')
    barcode = request.GET.get('barcode')

    queryset = TestValue.objects.all()

    if location_id:
        queryset = queryset.filter(locationId=location_id)

    if barcode:
        queryset = queryset.filter(barcode=barcode)

    serializer = TestValueSerializer(queryset, many=True)
    return Response(serializer.data)




import requests
LAB_API_URL = "http://127.0.0.1:1071/_b_a_c_k_e_n_d/Diagnostics/get-test-value/"
@api_view(['GET'])
def get_test_values(request):
    franchise_id = request.GET.get('franchise_id')
    date = request.GET.get('date')
    if not franchise_id or not date:
        return Response({"error": "franchise_id and date are required"}, status=400)
    try:
        # :white_check_mark: 1. Fetch test values from external LAB API
        response = requests.get(
            LAB_API_URL,
            params={"franchise_id": franchise_id, "date": date}
        )
        response.raise_for_status()
        test_data = response.json()
        # :white_check_mark: 2. Extract barcode from test_data
        barcode = None
        if isinstance(test_data, dict) and "data" in test_data and isinstance(test_data["data"], list):
            for item in test_data["data"]:
                if "barcode" in item:
                    barcode = item["barcode"]
                    break
        if not barcode:
            return Response({"error": "No barcode found in test data"}, status=404)
        # :white_check_mark: 3. Connect to MongoDB and get patient_id using barcode
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        franchise_register_collection = db["franchise_register"]
        register_data = franchise_register_collection.find_one({"barcode": barcode})
        if not register_data:
            return Response({"error": "No patient found with barcode: {}".format(barcode)}, status=404)
        patient_id = register_data.get("patient_id")
        # :mag: 3b. Get patient name from franchise_patient using patient_id
        franchise_patient_collection = db["franchise_patient"]
        patient_data = franchise_patient_collection.find_one({"patient_id": patient_id})
        patient_name = patient_data.get("patientname") if patient_data else None
        # :white_check_mark: 4. Return patient_id and test results
        return Response({
            "patient_id": patient_id,
            "patientname": patient_name,
            "barcode": barcode,
            "test_data": test_data
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)



LAB_API_URL = "http://127.0.0.1:1071/_b_a_c_k_e_n_d/Diagnostics/get-test-value/"
@api_view(['GET'])
def get_patient_by_barcode(request):
    franchise_id = request.GET.get('franchise_id')
    date = request.GET.get('date')
    if not franchise_id or not date:
        return Response({"error": "franchise_id and date are required"}, status=400)
    try:
        # Step 1: Fetch test data from external LAB API
        response = requests.get(
            LAB_API_URL,
            params={"franchise_id": franchise_id, "date": date}
        )
        response.raise_for_status()
        test_data = response.json()
        # Step 2: Extract barcode from test_data
        barcode = None
        if isinstance(test_data, dict) and "data" in test_data:
            for item in test_data["data"]:
                if "barcode" in item:
                    barcode = item["barcode"]
                    break
        if not barcode:
            return Response({"error": "No barcode found in test data"}, status=404)
        # Step 3: Connect to MongoDB and get patient data using barcode
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        register_data = db["franchise_register"].find_one({"barcode": barcode})
        if not register_data:
            return Response({"error": f"No patient found with barcode: {barcode}"}, status=404)
        patient_id = register_data.get("patient_id")
        # Step 4: Fetch patient name from franchise_patient
        patient_data = db["franchise_patient"].find_one({"patient_id": patient_id})
        patient_name = patient_data.get("patientname") if patient_data else None
        # Final response
        return Response({
            "franchise_id": franchise_id,
            "date": date,
            "barcode": barcode,
            "patient_id": patient_id,
            "patientname": patient_name,
            "test_data": test_data
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)