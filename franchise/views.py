# views.py
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from pyauth.auth import HasRolePermission
from rest_framework import status
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view , permission_classes
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, Http404
from django.core.files.base import ContentFile
from pyauth.auth import HasRolePermission
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import json
import os
import uuid
from bson.json_util import dumps, loads
from dotenv import load_dotenv


from .models import Franchise,FranchiseLocation, BarcodeRange,barcodestock
from .serializers import FranchiseSerializer,FranchiseLocationSerializer, BarcodestockSerializer
load_dotenv()

@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
@parser_classes([MultiPartParser])
def register_franchise(request):
    data = request.data.copy()
    print("Received data:", data)  # Debugging line

    # Get files from request
    aadhaar_file = request.FILES.get('aadhaar_proof')
    payment_file = request.FILES.get('payment_proof')
    agreement_file = request.FILES.get('agreement_proof')
    franchise_photo_file = request.FILES.get('franchise_photo')
    user_id  = data.get('auth-user-id')
    print("User ID from request:", user_id)  # Debugging line
    # MongoDB connection
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    fs = gridfs.GridFS(db)

    try:
        # Save uploaded files in GridFS and update data dict with file IDs
        user_id =  data.get('auth-user-id')
        if aadhaar_file:
            file_id = fs.put(aadhaar_file.read(), filename=aadhaar_file.name, content_type=aadhaar_file.content_type)
            data['aadhaar_file_id'] = str(file_id)

        if payment_file:
            file_id = fs.put(payment_file.read(), filename=payment_file.name, content_type=payment_file.content_type)
            data['payment_file_id'] = str(file_id)

        if agreement_file:
            file_id = fs.put(agreement_file.read(), filename=agreement_file.name, content_type=agreement_file.content_type)
            data['agreement_file_id'] = str(file_id)

        if franchise_photo_file:
            file_id = fs.put(franchise_photo_file.read(), filename=franchise_photo_file.name, content_type=franchise_photo_file.content_type)
            data['franchise_photo_file_id'] = str(file_id)
        data['createdby'] = data.get('createdby', user_id)
        data['lastmodifiedby'] = data.get('lastmodifiedby', user_id)
        # Validate and save Franchise model data
        serializer = FranchiseSerializer(data=data)
        if serializer.is_valid():
            franchise_data = serializer.save()
       
            franchise_id = data.get('franchise_id')
            if not franchise_id:
                return Response({
                    'error': 'Franchise ID is required for registration'
                }, status=status.HTTP_400_BAD_REQUEST)

            dummy_password = str(uuid.uuid4())[:8]
            hashed_password = make_password(dummy_password)
            reset_token = str(uuid.uuid4())

            franchise_user_collection = db["franchise_user"]
            franchise_user_data = {
                "franchise_id": franchise_id,
                "password": hashed_password,
                "reset_password": True,
                "reset_token": reset_token,
                "reset_token_expires": datetime.utcnow() + timedelta(hours=72),
                "created_date": datetime.utcnow(),
                "created_by": user_id,
                "lastmodified_by": user_id,
                "lastmodified_date": datetime.utcnow()
            }

            franchise_user_collection.insert_one(franchise_user_data)

            send_franchise_welcome_email(
                email=data.get('email'),
                franchise_id=franchise_id,
                reset_token=reset_token,
                franchise_name=data.get('franchiser_name', 'Franchise Partner')
            )

            return Response({
                'message': 'Franchise registered successfully. Password reset email sent.',
                'franchise_id': franchise_id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            'error': f'Registration failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        client.close()



def send_franchise_welcome_email(email, franchise_id, reset_token, franchise_name):
    """Send welcome email with password reset link"""
    try:
        # Create password reset link
        reset_link = f"{os.getenv('FRONTEND_URL', 'http://127.0.0.1:8000')}/franchise/reset-password?token={reset_token}&franchise_id={franchise_id}"
        
        # Email context
        context = {
            'franchise_name': franchise_name,
            'franchise_id': franchise_id,  # Use franchise_id instead of employee_id
            'reset_link': reset_link,
            'expiry_hours': 72
        }
        
        # Render email template
        html_message = render_to_string('email/franchise_welcome.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject='Welcome to Shanmuga Franchise - Set Your Password',
            message=plain_message,
            from_email=os.getenv('EMAIL_FROM', 'noreply@shanmugafranchise.com'),
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"Welcome email sent successfully to {email}")
        
    except Exception as e:
        print(f"Failed to send email to {email}: {str(e)}")

# HTML view for password reset form
@permission_classes([HasRolePermission])
def reset_password_form(request):
    """Display password reset form"""
    token = request.GET.get('token')
    franchise_id = request.GET.get('franchise_id')  # Changed from employee_id
    
    if not token or not franchise_id:
        return render(request, 'email/error.html', {
            'error': 'Invalid reset link. Token and franchise ID are required.'
        })
    
    # Validate token first
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    franchise_user_collection = db["franchise_user"]
    
    try:
        user = franchise_user_collection.find_one({
            "franchise_id": franchise_id,  # Changed from employeeId
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })
        
        if not user:
            return render(request, 'email/error.html', {
                'error': 'Invalid or expired reset token. Please request a new password reset link.'
            })
        
        context = {
            'token': token,
            'franchise_id': franchise_id,  # Changed from employee_id
            'email': user.get('email', '')
        }
        
        return render(request, 'email/reset_password.html', context)
        
    except Exception as e:
        return render(request, 'email/error.html', {
            'error': f'An error occurred: {str(e)}'
        })
    finally:
        client.close()

# API endpoint for password reset
@csrf_exempt
@permission_classes([HasRolePermission])
def reset_franchise_password(request):
    """Handle password reset for franchise users"""
    if request.method == 'POST':
        token = request.POST.get('token')
        franchise_id = request.POST.get('franchise_id')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not all([token, franchise_id, new_password, confirm_password]):
            messages.error(request, 'All fields are required')
            return redirect(f'/franchise/reset-password?token={token}&franchise_id={franchise_id}')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return redirect(f'/franchise/reset-password?token={token}&franchise_id={franchise_id}')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long')
            return redirect(f'/franchise/reset-password?token={token}&franchise_id={franchise_id}')

        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        user_collection = db["franchise_user"]
        franchise_collection = db["franchise_franchise"] 

        try:
            user = user_collection.find_one({
                "franchise_id": franchise_id,
                "reset_token": token,
                "reset_token_expires": {"$gt": datetime.utcnow()}
            })

            if not user:
                messages.error(request, 'Invalid or expired reset token')
                return redirect(f'/franchise/reset-password?token={token}&franchise_id={franchise_id}')

            hashed_password = make_password(new_password)

            # ✅ Update user's password
            user_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "password": hashed_password,
                        "reset_password": False,
                        "lastmodified_date": datetime.utcnow(),
                        "lastmodified_by": franchise_id
                    },
                    "$unset": {
                        "reset_token": "",
                        "reset_token_expires": ""
                    }
                }
            )

            # ✅ Activate the related franchise
            franchise_collection.update_one(
                {"franchise_id": franchise_id},
                {"$set": {"is_active": True}}
            )

            return render(request, 'email/success.html', {
                'message': 'Password updated successfully. Your account is now active.',
                'franchise_id': franchise_id
            })

        except Exception as e:
            messages.error(request, f'Password reset failed: {str(e)}')
            return redirect(f'/franchise/reset-password?token={token}&franchise_id={franchise_id}')
        finally:
            client.close()

    return reset_password_form(request)

@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def validate_reset_token(request):
    """Validate if reset token is still valid"""
    token = request.GET.get('token')
    franchise_id = request.GET.get('franchise_id')  # Changed from employee_id
    
    if not token or not franchise_id:
        return Response({
            'error': 'Token and franchise ID are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # MongoDB connection
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    franchise_user_collection = db["franchise_user"]
    
    try:
        user = franchise_user_collection.find_one({
            "franchise_id": franchise_id,  # Changed from employeeId
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })
        
        if user:
            return Response({
                'valid': True,
                'franchise_id': franchise_id  # Changed from employee_id
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'valid': False,
                'error': 'Invalid or expired token'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Validation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        client.close()


@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_registered_franchise(request):
    try:
        franchises = Franchise.objects.all()
        serializer = FranchiseSerializer(franchises, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

    
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_inactive_franchise_locations(request):
    try:
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]

        # Collections
        franchise_collection = db["franchise_franchise"]
        location_collection = db["franchise_location_details"]

        # Step 1: Get all ACTIVE franchise location_ids
        active_franchises = franchise_collection.find({ "is_active": True }, { "location_id": 1 })
        active_location_ids = [item["location_id"] for item in active_franchises if "location_id" in item]

        # Step 2: Find all location documents that are either inactive or belong to inactive franchises
        # Meaning: include records where location_id NOT in active_location_ids
        data = list(location_collection.find({
            "location_id": { "$nin": active_location_ids }
        }))

        json_data = dumps(data, indent=2)
        return HttpResponse(json_data, content_type="application/json")

    except Exception as e:
        return HttpResponse(
            dumps({ "error": str(e) }),
            content_type="application/json",
            status=500
        )

    

#toggle the loctaion true or false
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_all_franchise_locations(request):
    try:
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_location_details"]

        data = list(collection.find())

        # Convert _id and datetime properly
        for item in data:
            item["_id"] = str(item["_id"])
            if "created_date" in item:
                item["created_date"] = item["created_date"].isoformat()
            if "lastmodified_date" in item:
                item["lastmodified_date"] = item["lastmodified_date"].isoformat()

        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({ "error": str(e) }, status=500)


@csrf_exempt
@api_view(['GET'])
# @permission_classes([HasRolePermission])
def get_file(request, file_id):
    """
    Retrieve file from GridFS by file_id
    """
    try:
        # MongoDB connection
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        fs = gridfs.GridFS(db)
        
        # Get file from GridFS
        file_obj = fs.get(ObjectId(file_id))
        
        # Create HTTP response with file content
        response = HttpResponse(
            file_obj.read(),
            content_type=file_obj.content_type or 'application/octet-stream'
        )
        
        # Set filename in response header
        response['Content-Disposition'] = f'inline; filename="{file_obj.filename}"'
        
        return response
        
    except gridfs.NoFile:
        return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def update_franchise_status(request, location_id):
    try:
        # Connect to MongoDB
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_location_details"]
        user_id = request.headers.get("auth-user-id")
        # Parse the ObjectId
        object_id = ObjectId(location_id)
        
        # Get is_active value from request body
        is_active = request.data.get("is_active")

        # Update the document
        result = collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "is_active": is_active,
                    "lastmodified_by": user_id,
                    "lastmodified_date": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            return JsonResponse({"error": "Franchise location not found."}, status=404)

        return JsonResponse({"message": "Status updated successfully."}, status=200)

    except Exception as e:
        print("Error:", str(e))
        return JsonResponse({"error": "Something went wrong."}, status=500)


@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def toggle_franchise_status(request, franchise_id):
    try:
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_franchise"]
        user_id = request.headers.get("auth-user-id")

        franchise = collection.find_one({"franchise_id": franchise_id})
        if not franchise:
            return Response({"error": "franchise not found"}, status=status.HTTP_404_NOT_FOUND)

        # Toggle is_active
        new_status = not franchise.get("is_active", True)

        collection.update_one(
            {"franchise_id": franchise_id},
            {
                "$set": {
                    "is_active": new_status,
                    "lastmodified_by": user_id,
                    "lastmodified_date": datetime.utcnow()
                }
            }
        )


        return Response({"message": "Status updated", "is_active": new_status}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET"])
@permission_classes([HasRolePermission])
def get_franchise(request, franchise_id):
    """
    Get details of a specific franchise by franchise_id
    """
    try:
        franchise = get_object_or_404(Franchise, franchise_id=franchise_id)
        
        # Convert model instance to dictionary
        franchise_data = {

            'franchise_id': franchise.franchise_id,
            'franchiser_name': franchise.franchise_name,
            'location': franchise.location_id,
            'contact_no': franchise.contact_no,
            'email': franchise.email,
            'alt_number': franchise.alt_number,
            'address': franchise.address,
            'qualification': franchise.qualification,
            'age': franchise.age,
            'gender': franchise.gender,
            'pincode': franchise.pincode,
            'dob': franchise.dob.isoformat() if franchise.dob else None,
            'is_active': franchise.is_active,
            'aadhaar_file_id': franchise.aadhaar_file_id,
            'payment_file_id': franchise.payment_file_id,
            'agreement_file_id': franchise.agreement_file_id,
            'franchise_photo_file_id': franchise.franchise_photo_file_id,
        }
        
        return JsonResponse(franchise_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



# Custom JSON encoder to convert ObjectId → str
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# -----------------------------------------------------------------------------
# PUT/PATCH /update_franchise/<franchise_id>/
# -----------------------------------------------------------------------------
from gridfs import GridFS
@csrf_exempt
@require_http_methods(["POST"])
@permission_classes([HasRolePermission])
def update_franchise(request, franchise_id):
    """
    Update franchise details (in MongoDB) by franchise_id.
    Replaces any ORM/serializer usage with direct pymongo calls.
    """
    try:
        # 1) Connect to MongoDB
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        collection = db["franchise_franchise"]
        fs = GridFS(db)

        # 2) First, check that a document with this franchise_id exists
        existing = collection.find_one({"franchise_id": franchise_id})
        if not existing:
            raise Http404(f"No franchise found with franchise_id={franchise_id}")

        # 3) Build a dict of fields to set
        update_fields = {}

        # Text fields in request.POST
        text_keys = [
            "franchiser_name",
            "location",
            "contact_no",
            "email",
            "alt_number",
            "address",
            "qualification",
            "age",
            "gender",
            "pincode",
            "dob",
        ]
        for key in text_keys:
            if key in request.POST:
                val = request.POST.get(key)
                if key == "age":
                    try:
                        val = int(val)
                    except ValueError:
                        continue
                if key == "dob":
                    try:
                        val = datetime.fromisoformat(val)
                    except Exception:
                        pass
                update_fields[key] = val

        # Handle is_active separately
        if "is_active" in request.POST:
            is_active_str = request.POST.get("is_active").lower()
            update_fields["is_active"] = (is_active_str == "true")

        # 4) Handle file uploads
        file_fields_map = {
            "aadhaar_file": "aadhaar_file_id",
            "payment_file": "payment_file_id",
            "agreement_file": "agreement_file_id",
            "franchise_photo": "franchise_photo_file_id",
        }
        for incoming_name, mongo_field in file_fields_map.items():
            if incoming_name in request.FILES:
                uploaded_file = request.FILES[incoming_name]
                file_id = fs.put(
                    uploaded_file.read(),
                    filename=uploaded_file.name,
                    content_type=uploaded_file.content_type
                )
                update_fields[mongo_field] = str(file_id)

        # ✅ Add audit fields
        user_id = request.headers.get("auth-user-id", "system")
        update_fields["lastmodifiedby"] = user_id
        update_fields["lastmodifieddate"] = datetime.utcnow()

        # 5) Run the update
        if update_fields:
            collection.update_one(
                {"franchise_id": franchise_id},
                {"$set": update_fields}
            )

        # 6) Retrieve updated document
        updated = collection.find_one({"franchise_id": franchise_id})
        if not updated:
            raise Http404(f"franchise vanished after update: franchise_id={franchise_id}")

        # 7) Prepare JSON response
        result = {}
        for k, v in updated.items():
            if isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, datetime):
                result[k] = v.isoformat()
            else:
                result[k] = v

        return JsonResponse(result, encoder=MongoJSONEncoder, safe=False)

    except Http404 as e:
        return JsonResponse({"error": str(e)}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@permission_classes([HasRolePermission])
def generate_next_franchise_id(collection):
    last_franchise = Franchise.objects.order_by('-franchise_id').first()
    
    if last_franchise:
        last_id_num = int(last_franchise.franchise_id.replace('SHF', ''))
        next_id_num = last_id_num + 1
    else:
        next_id_num = 1  # start from SHF001 if no data exists

    next_franchise_id = f'SHF{next_id_num:03d}'  # Pads with leading zeros

    return JsonResponse({'franchise_id': next_franchise_id})


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from .models import BarcodeRange
from .serializers import BarcodeRangeSerializer


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_all_barcodes(request):
    barcodes = BarcodeRange.objects.all().order_by('-createdAt')
    serializer = BarcodeRangeSerializer(barcodes, many=True)
    return Response(serializer.data)



from rest_framework.decorators import api_view
from rest_framework.response import Response
from bson import ObjectId
from pymongo import MongoClient
import os

@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def update_barcode_status(request, barcode_id):
    try:
        mongo_url = os.getenv("MONGO_URL")
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
    

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import BarcodestockSerializer

@api_view(['POST'])
@permission_classes([HasRolePermission])
def savestockbarcode(request):
    

    data = request.data.copy()  # Make the data mutable
    user_id  = data.get('auth-user-id')
    data['createdby'] = user_id  # Set createdby manually

    serializer = BarcodestockSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Barcode stock saved successfully'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Franchise
from .serializers import FranchiseSerializer

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_franchises(request):
    franchises = Franchise.objects.all()
    serializer = FranchiseSerializer(franchises, many=True)
    return Response(serializer.data)



import os
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect
from django.contrib import messages
from dotenv import load_dotenv
import gridfs
from .models import Franchise
from .serializers import FranchiseSerializer

load_dotenv()

# Your existing code remains the same...
# (register_franchise, send_franchise_welcome_email, reset_password_form, etc.)

@csrf_exempt
@api_view(['POST'])
# @permission_classes([HasRolePermission])
def resend_password_reset_email(request):
    """Resend password reset email for inactive franchises"""
    franchise_id = request.data.get('franchise_id')
    
    if not franchise_id:
        return Response({
            'error': 'Franchise ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    franchise_user_collection = db["franchise_user"]
    franchise_collection = db["franchise_franchise"]
    
    try:
        # Check if franchise user exists and needs password reset
        user = franchise_user_collection.find_one({
            "franchise_id": franchise_id,
            "reset_password": True
        })
        
        if not user:
            return Response({
                'error': 'Franchise not found or already activated'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get franchise details for email
        franchise = franchise_collection.find_one({"franchise_id": franchise_id})
        if not franchise:
            return Response({
                'error': 'Franchise details not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Generate new reset token and expiry
        new_reset_token = str(uuid.uuid4())
        new_expiry = datetime.utcnow() + timedelta(hours=72)
        
        # Update user with new token and expiry
        franchise_user_collection.update_one(
            {"franchise_id": franchise_id},
            {
                "$set": {
                    "reset_token": new_reset_token,
                    "reset_token_expires": new_expiry,
                }
            }
        )
        
        # Send reminder email
        send_franchise_reminder_email(
            email=franchise.get('email'),
            franchise_id=franchise_id,
            reset_token=new_reset_token,
            franchise_name=franchise.get('franchiser_name', 'Franchise Partner')
        )
        
        return Response({
            'message': 'Password reset email resent successfully',
            'franchise_id': franchise_id,
            'new_expiry': new_expiry.isoformat()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to resend email: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        client.close()

def send_franchise_reminder_email(email, franchise_id, reset_token, franchise_name):
    """Send reminder email for password reset"""
    try:
        # Create password reset link
        reset_link = f"{os.getenv('FRONTEND_URL', 'http://127.0.0.1:8000')}/franchise/reset-password?token={reset_token}&franchise_id={franchise_id}"
        
        # Email context
        context = {
            'franchise_name': franchise_name,
            'franchise_id': franchise_id,
            'reset_link': reset_link,
            'expiry_hours': 72,
            'is_reminder': True
        }
        
        # Render email template
        html_message = render_to_string('email/franchise_reminder.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject='Reminder: Complete Your Shanmuga Franchise Account Setup',
            message=plain_message,
            from_email=os.getenv('EMAIL_FROM', 'noreply@shanmugafranchise.com'),
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"Reminder email sent successfully to {email}")
        
    except Exception as e:
        print(f"Failed to send reminder email to {email}: {str(e)}")

@api_view(['GET'])
# @permission_classes([HasRolePermission])
def inactive_franchises(request):
    """Get list of inactive franchises with additional details"""
    try:
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        user_collection = db["franchise_user"]
        franchise_collection = db["franchise_franchise"]
        
        # Fetch users where reset_password is True
        users = list(user_collection.find({"reset_password": True}))
        
        # Enrich with franchise details
        enriched_users = []
        for user in users:
            user["_id"] = str(user["_id"])
            
            # Get franchise details
            franchise = franchise_collection.find_one({"franchise_id": user["franchise_id"]})
            if franchise:
                user["franchise_name"] = franchise.get("franchise_name", "Unknown")
                user["email"] = franchise.get("email", "No email")
                user["phone"] = franchise.get("phone", "No phone")
                user["location"] = franchise.get("location", "No location")
            
            # Check if token is expired
            if user.get("reset_token_expires"):
                user["is_expired"] = user["reset_token_expires"] < datetime.utcnow()
            else:
                user["is_expired"] = True
                
            enriched_users.append(user)
        
        return Response(enriched_users)
        
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    finally:
        client.close()

# Bulk resend functionality
@csrf_exempt
@api_view(['POST'])
# @permission_classes([HasRolePermission])
def bulk_resend_password_reset_emails(request):
    """Resend password reset emails to multiple franchises"""
    franchise_ids = request.data.get('franchise_ids', [])
    
    if not franchise_ids or not isinstance(franchise_ids, list):
        return Response({
            'error': 'franchise_ids array is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    franchise_user_collection = db["franchise_user"]
    franchise_collection = db["franchise_franchise"]
    
    success_count = 0
    failed_franchises = []
    
    try:
        for franchise_id in franchise_ids:
            try:
                # Check if franchise user exists and needs password reset
                user = franchise_user_collection.find_one({
                    "franchise_id": franchise_id,
                    "reset_password": True
                })
                
                if not user:
                    failed_franchises.append({
                        'franchise_id': franchise_id,
                        'error': 'Franchise not found or already activated'
                    })
                    continue
                
                # Get franchise details
                franchise = franchise_collection.find_one({"franchise_id": franchise_id})
                if not franchise:
                    failed_franchises.append({
                        'franchise_id': franchise_id,
                        'error': 'Franchise details not found'
                    })
                    continue
                
                # Generate new reset token and expiry
                new_reset_token = str(uuid.uuid4())
                new_expiry = datetime.utcnow() + timedelta(hours=72)
                
                # Update user with new token and expiry
                franchise_user_collection.update_one(
                    {"franchise_id": franchise_id},
                    {
                        "$set": {
                            "reset_token": new_reset_token,
                            "reset_token_expires": new_expiry,
                            "lastmodified_date": datetime.utcnow(),
                            "lastmodified_by": request.auth_metadata.get('auth-user-id', 'system')
                        }
                    }
                )
                
                # Send reminder email
                send_franchise_reminder_email(
                    email=franchise.get('email'),
                    franchise_id=franchise_id,
                    reset_token=new_reset_token,
                    franchise_name=franchise.get('franchiser_name', 'Franchise Partner')
                )
                
                success_count += 1
                
            except Exception as e:
                failed_franchises.append({
                    'franchise_id': franchise_id,
                    'error': str(e)
                })
        
        return Response({
            'message': f'Bulk resend completed. {success_count} emails sent successfully.',
            'success_count': success_count,
            'failed_count': len(failed_franchises),
            'failed_franchises': failed_franchises
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Bulk resend failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        client.close()



#franchise request the test cancellation status:cancel Accepted
import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient

@csrf_exempt
def update_test_status(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        # Parse request data
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        barcode = data.get('barcode')
        test_name = data.get('test_name')
        new_status = data.get('new_status')
        
        # Validate required fields
        if not all([patient_id, barcode, test_name, new_status]):
            return JsonResponse({
                "error": "Missing required fields: patient_id, barcode, test_name, new_status"
            }, status=400)
        
        # Connect to MongoDB
        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        franchise_collection = db["franchise_billing"]
        
        # Find the document
        document = franchise_collection.find_one({
            "patient_id": patient_id,
            "barcode": barcode
        })
        
        if not document:
            return JsonResponse({
                "error": "Document not found"
            }, status=404)
        
        # Parse testdetails
        if "testdetails" not in document or not document["testdetails"]:
            return JsonResponse({
                "error": "No test details found"
            }, status=404)
        
        try:
            # First parse to remove outer quotes
            testdetails_str = json.loads(document["testdetails"])  
            
            # If still string, parse again
            if isinstance(testdetails_str, str):
                testdetails = json.loads(testdetails_str)
            else:
                testdetails = testdetails_str
        except Exception as e:
            return JsonResponse({
                "error": f"Error parsing testdetails: {str(e)}"
            }, status=400)
        
        # Find and update the specific test
        test_found = False
        for test in testdetails:
            if test.get("test_name") == test_name:
                test["status"] = new_status
                test_found = True
                break
        
        if not test_found:
            return JsonResponse({
                "error": "Test not found"
            }, status=404)
        
        # Convert back to string format (double JSON encoding to match your format)
        updated_testdetails = json.dumps(json.dumps(testdetails))
        
        # Update the document
        result = franchise_collection.update_one(
            {
                "patient_id": patient_id,
                "barcode": barcode
            },
            {
                "$set": {"testdetails": updated_testdetails}
            }
        )
        
        if result.modified_count == 1:
            return JsonResponse({
                "message": "Test status updated successfully",
                "patient_id": patient_id,
                "barcode": barcode,
                "test_name": test_name,
                "new_status": new_status
            }, status=200)
        else:
            return JsonResponse({
                "error": "Failed to update document"
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({
            "error": f"Internal server error: {str(e)}"
        }, status=500)
    finally:
        if 'client' in locals():
            client.close()




# Updated get_cancel_requested_tests function to exclude already processed tests
@csrf_exempt
def get_cancel_requested_tests(request):
    mongo_url = os.getenv("MONGO_URL")
    client = MongoClient(mongo_url)
    db = client["franchise"]
    franchise_collection = db["franchise_billing"]

    results = []
    for doc in franchise_collection.find():
        if "testdetails" in doc and doc["testdetails"]:
            try:
                # First parse to remove outer quotes
                testdetails_str = json.loads(doc["testdetails"])  
                
                # If still string, parse again
                if isinstance(testdetails_str, str):
                    testdetails = json.loads(testdetails_str)
                else:
                    testdetails = testdetails_str

                # Include both 'Cancel Requested' and 'Cancel Accepted' for tracking
                cancel_requested = [
                    test for test in testdetails 
                    if test.get("status") in ["Cancel Requested", "Cancel Accepted", "Rejected"]
                ]
                
                if cancel_requested:
                    results.append({
                        "patient_id": doc.get("patient_id"),
                        "barcode": doc.get("barcode"),
                        "referredDoctor": doc.get("referredDoctor"),
                        "franchise_id": doc.get("franchise_id"),
                        "cancel_requested_tests": cancel_requested
                    })
            except Exception as e:
                print("Error parsing testdetails:", e, doc.get("_id"))

    client.close()
    return JsonResponse({"cancel_requested": results}, safe=False)


#prabhu sir and priya mam final Approved status:cancel Approved
@csrf_exempt
def update_cancel_status(request):

    """
    Approve or Reject a Cancel Accepted test
    """

    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        patient_id = data.get("patient_id")
        test_id = data.get("test_id")
        action = data.get("action")  # "approve" or "reject"

        if not (patient_id and test_id and action):
            return JsonResponse(
                {"error": "patient_id, test_id and action are required"}, status=400
            )

        mongo_url = os.getenv("MONGO_URL")
        client = MongoClient(mongo_url)
        db = client["franchise"]
        franchise_collection = db["franchise_billing"]
        franchise_revenue_collection = db["franchise_franchisemonthlyrevenue"]

        patient = franchise_collection.find_one({"patient_id": patient_id})
        if not patient:
            return JsonResponse({"error": "Patient not found"}, status=404)

        # Parse testdetails safely (triple JSON decode)
        raw = patient.get("testdetails", "[]")
        testdetails = raw
        for _ in range(3):  # try decoding up to 3 levels
            if isinstance(testdetails, str):
                try:
                    testdetails = json.loads(testdetails)
                except Exception:
                    break
            else:
                break

        if not isinstance(testdetails, list):
            return JsonResponse({"error": "testdetails is not a list"}, status=400)

        # Update test status
        updated = False
        cancelled_test = None
        for test in testdetails:
            if str(test.get("test_id")) == str(test_id) and test.get("status") in ["Cancel Accepted"]:
                if action == "approve":
                    test["status"] = "Cancel Approved"
                    test["cancel_approved_date"] = datetime.utcnow().isoformat()
                    cancelled_test = test  # Store the cancelled test for amount calculations
                elif action == "reject":
                    test["status"] = "Reject"
                    test["rejected_date"] = datetime.utcnow().isoformat()
                updated = True
                break

        if not updated:
            return JsonResponse(
                {"error": "No matching test with status 'Cancel Accepted'"}, status=404
            )

        if action == "approve" and cancelled_test:
            # Get test MRP and discount percentage
            test_mrp = float(cancelled_test.get("MRP", 0))
            discount_percentage = float(cancelled_test.get("discountPercentage", 0))

            # Calculate discounted amount
            discount_amount = (test_mrp * discount_percentage) / 100
            final_amount = test_mrp - discount_amount

            # 2. Update billing table - minus the amount from total_amount and net_amount
            # (pipeline update so it works whether these are Decimal128, double, or string)
            franchise_collection.update_one(
                {"patient_id": patient_id},
                [
                    {
                        "$set": {
                            "total": {
                                "$subtract": [
                                    {"$toDouble": {"$ifNull": ["$total", 0]}},
                                    final_amount
                                ]
                            },
                            "netAmount": {
                                "$subtract": [
                                    {"$toDouble": {"$ifNull": ["$netAmount", 0]}},
                                    final_amount
                                ]
                            }
                        }
                    }
                ]
            )

            # 3. Update franchisemonthlyrevenue table
            franchise_id = patient.get("franchise_id")
            current_date = datetime.utcnow()
            month = current_date.month
            year = current_date.year

            if franchise_id:
                # Calculate revenue shares (assuming equal split, adjust as needed)
                franchise_share = final_amount * 0.5   # 50% to franchise
                franchiser_share = final_amount * 0.5  # 50% to franchiser (matches DB field name)

                franchise_revenue_collection.update_one(
                    {
                        "franchise_id": franchise_id,
                        "month": month,
                        "year": year
                    },
                    [
                        {
                            "$set": {
                                "franchise_share": {
                                    "$subtract": [
                                        {"$toDouble": {"$ifNull": ["$franchise_share", 0]}},
                                        franchise_share
                                    ]
                                },
                                "franchiser_share": {
                                    "$subtract": [
                                        {"$toDouble": {"$ifNull": ["$franchiser_share", 0]}},
                                        franchiser_share
                                    ]
                                },
                                "total_revenue": {
                                    "$subtract": [
                                        {"$toDouble": {"$ifNull": ["$total_revenue", 0]}},
                                        final_amount
                                    ]
                                }
                            }
                        }
                    ]
                )

        # Save back (double encode again to match your schema)
        updated_testdetails = json.dumps(testdetails)  # single dump

        franchise_collection.update_one(
            {"patient_id": patient_id},
            {
                "$set": {
                    "testdetails": updated_testdetails,
                    "lastmodified_date": datetime.utcnow()
                }
            }
        )

        return JsonResponse(
            {"success": True, "message": f"Cancel request {action}d successfully"}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        if "client" in locals():
            client.close()

import os
from bson.decimal128 import Decimal128
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient

@csrf_exempt
def month_end_calculation(request):
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client["franchise"]

    def safe_float(value):
        """Safely convert Decimal128, string, or numeric types to float"""
        if isinstance(value, Decimal128):
            return float(value.to_decimal())
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    # Handle POST request - can be for all or single franchise
    if request.method == "POST":
        try:
            body = json.loads(request.body) if request.body else {}
            franchise_id = body.get("franchise_id")
            month = body.get("month")
            year = body.get("year")
        except json.JSONDecodeError:
            franchise_id = None
            month = None
            year = None

        # If specific franchise, month, year provided - close that one
        if franchise_id and month and year:
            monthly_doc = db["franchise_franchisemonthlyrevenue"].find_one({
                "franchise_id": franchise_id,
                "month": month,
                "year": year
            })
            wallet_doc = db["franchise_wallet"].find_one({"franchise_id": franchise_id})

            if monthly_doc and wallet_doc:
                total_revenue = safe_float(monthly_doc.get("total_revenue", 0))
                franchiser_share = safe_float(monthly_doc.get("franchise_share", 0))
                wallet_balance = safe_float(wallet_doc.get("balance", 0))
                calculated_value = wallet_balance - (total_revenue - franchiser_share)

                # Update wallet
                db["franchise_wallet"].update_one(
                    {"franchise_id": franchise_id},
                    {
                        "$set": {
                            "balance": calculated_value,
                            "updated_date": datetime.utcnow()
                        }
                    }
                )

                # Mark as closed
                db["franchise_franchisemonthlyrevenue"].update_one(
                    {"franchise_id": franchise_id, "month": month, "year": year},
                    {
                        "$set": {
                            "status": "closed",
                            "closed_date": datetime.utcnow()
                        }
                    }
                )

                message = f"Franchise {franchise_id} closed successfully for {month}/{year}"
            else:
                message = "Franchise or wallet not found"
        else:
            # Close all active franchises
            franchise_ids = db["franchise_franchisemonthlyrevenue"].distinct("franchise_id")
            
            for fid in franchise_ids:
                monthly_doc = db["franchise_franchisemonthlyrevenue"].find_one(
                    {"franchise_id": fid},
                    sort=[("created_date", -1)]
                )
                
                # Only process if status is active
                if monthly_doc and monthly_doc.get("status") == "active":
                    wallet_doc = db["franchise_wallet"].find_one({"franchise_id": fid})
                    
                    if wallet_doc:
                        total_revenue = safe_float(monthly_doc.get("total_revenue", 0))
                        franchiser_share = safe_float(monthly_doc.get("franchise_share", 0))
                        wallet_balance = safe_float(wallet_doc.get("balance", 0))
                        calculated_value = wallet_balance - (total_revenue - franchiser_share)

                        # Update wallet
                        db["franchise_wallet"].update_one(
                            {"franchise_id": fid},
                            {
                                "$set": {
                                    "balance": calculated_value,
                                    "updated_date": datetime.utcnow()
                                }
                            }
                        )

                        # Mark as closed
                        db["franchise_franchisemonthlyrevenue"].update_one(
                            {
                                "franchise_id": fid, 
                                "month": monthly_doc.get("month"), 
                                "year": monthly_doc.get("year")
                            },
                            {
                                "$set": {
                                    "status": "closed",
                                    "closed_date": datetime.utcnow()
                                }
                            }
                        )

            message = "All active franchises closed successfully"

    # Get all data with status
    franchise_ids = db["franchise_franchisemonthlyrevenue"].distinct("franchise_id")
    results = []

    for franchise_id in franchise_ids:
        monthly_doc = db["franchise_franchisemonthlyrevenue"].find_one(
            {"franchise_id": franchise_id},
            sort=[("created_date", -1)]
        )
        wallet_doc = db["franchise_wallet"].find_one({"franchise_id": franchise_id})

        if not monthly_doc or not wallet_doc:
            continue

        total_revenue = safe_float(monthly_doc.get("total_revenue", 0))
        franchiser_share = safe_float(monthly_doc.get("franchise_share", 0))
        wallet_balance = safe_float(wallet_doc.get("balance", 0))
        calculated_value = wallet_balance - (total_revenue - franchiser_share)

        results.append({
            "franchise_id": franchise_id,
            "month": monthly_doc.get("month"),
            "year": monthly_doc.get("year"),
            "total_revenue": total_revenue,
            "franchise_share": franchiser_share,
            "wallet_balance": wallet_balance,
            "current_wallet_balance": calculated_value,
            "status": monthly_doc.get("status", "active")  # Default to active if not set
        })

    # Return response
    if request.method == "POST":
        return JsonResponse({"message": message, "data": results}, safe=False)
    return JsonResponse({"data": results}, safe=False)




"""
View for POST /post_loaction/

Creates a new franchise location document. Mirrors the pattern in your
snippet (request.data.copy(), auth-user-id -> created_by) and adds:

  1. Auto-incrementing location_id, based on the highest existing one
     (e.g. last is SDMF025 -> new one is SDMF026).
  2. created_by / created_date and lastmodified_by / lastmodified_date.
  3. is_active defaults to True.

Adjust the import of `location_collection` to match wherever you already
open your Mongo collection elsewhere in the app.
"""

import re
from datetime import datetime, timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .dbcollection import location_collection  

LOCATION_PREFIX = "SDMF"


def generate_next_location_id():
    """
    Finds the highest existing location_id with the SDMF prefix and
    returns the next one in the sequence, preserving zero-padding
    (SDMF025 -> SDMF026).

    Note: this does a find + increment, which is fine for normal usage
    but isn't atomic. If two requests can hit this at the exact same
    moment, you'd want a dedicated counters collection with
    find_one_and_update($inc) instead to avoid a duplicate ID.
    """
    last_location = location_collection.find_one(
        {"location_id": {"$regex": f"^{LOCATION_PREFIX}"}},
        sort=[("location_id", -1)],
    )

    if not last_location:
        return f"{LOCATION_PREFIX}001"

    match = re.search(r"(\d+)$", last_location["location_id"])
    last_number = int(match.group(1)) if match else 0
    padding = len(match.group(1)) if match else 3

    return f"{LOCATION_PREFIX}{str(last_number + 1).zfill(padding)}"


@api_view(['POST'])
def post_loaction(request):
    serializer = FranchiseLocationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_id = request.user.id
    now = datetime.now(timezone.utc)
    validated = serializer.validated_data

    # Build the model instance in memory only — do NOT call .save() on it,
    # there's no real table backing it (Meta.managed = False).
    location = FranchiseLocation(
        location_id=generate_next_location_id(),
        Cluster_Name=validated['Cluster_Name'],
        District=validated['District'],
        Covered_Areas=validated.get('Covered_Areas', ''),
        is_active=validated.get('is_active', True),
        created_by=user_id,
        created_date=now,
        lastmodified_by=user_id,
        lastmodified_date=now,
    )

    result = location_collection.insert_one(location.to_mongo_dict())
    response_data = location.to_mongo_dict()
    response_data["_id"] = str(result.inserted_id)

    return Response(response_data, status=status.HTTP_201_CREATED)


from datetime import datetime, timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_date
from django.utils import timezone


@api_view(['GET', 'PUT'])
def getandupdatebarcode(request):
    if request.method == 'GET':
        date_param = request.GET.get('date')
        if date_param:
            selected_date = parse_date(date_param)
            if not selected_date:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            selected_date = timezone.localdate()

        # Use a datetime range instead of __date lookup — __date needs
        # datetime_cast_date_sql(), which the mongo backend doesn't implement.
        tz = timezone.get_current_timezone()
        start_of_day = timezone.make_aware(
            datetime.combine(selected_date, datetime.min.time()), tz
        )
        end_of_day = start_of_day + timedelta(days=1)

        queryset = barcodestock.objects.filter(
            date__gte=start_of_day,
            date__lt=end_of_day
        ).order_by('-date')

        serializer = BarcodestockSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PUT':
        barcode_id = request.data.get('barcode_id')
        if not barcode_id:
            return Response(
                {'error': 'barcode_id is required to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            existing = barcodestock.objects.get(barcode_id=barcode_id)
        except barcodestock.DoesNotExist:
            return Response(
                {'error': 'No record found for this barcode_id.'},
                status=status.HTTP_404_NOT_FOUND
            )

        update_fields = {
            'startbarcode': request.data.get('startbarcode', existing.startbarcode),
            'endbarcode': request.data.get('endbarcode', existing.endbarcode),
            'modifedby': request.data.get('modifedby', ''),
            'modifieddatetime': timezone.now(),
        }

        # Atomic update by barcode_id — avoids Django's save()/_do_update()
        # insert-fallback quirk on the mongo backend, which was silently
        # creating a new document instead of updating the existing one.
        updated_count = barcodestock.objects.filter(barcode_id=barcode_id).update(**update_fields)

        if not updated_count:
            return Response(
                {'error': 'Update failed — no matching document.'},
                status=status.HTTP_404_NOT_FOUND
            )

        instance = barcodestock.objects.get(barcode_id=barcode_id)
        return Response(
            {'message': 'Barcode stock updated successfully', 'data': BarcodestockSerializer(instance).data},
            status=status.HTTP_200_OK
        )