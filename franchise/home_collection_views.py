from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import datetime
from pymongo import MongoClient
from bson import ObjectId
from django.conf import settings

def get_mongo_collection(collection_name='franchise_homecollection'):
    try:
        client_dict = settings.DATABASES['default']['CLIENT']
        host = client_dict.get('host', 'mongodb://localhost:27017/')
        db_name = settings.DATABASES['default'].get('NAME', 'franchise')
        client = MongoClient(host)
        return client[db_name][collection_name]
    except Exception as e:
        print("Mongo connection error:", e)
        return None

def get_franchise_name_map():
    name_map = {}
    try:
        col_franchise = get_mongo_collection('franchise_franchise')
        col_location = get_mongo_collection('franchise_location_details')
        if col_franchise is not None:
            loc_map = {}
            if col_location is not None:
                for loc in col_location.find():
                    loc_id = loc.get('location_id')
                    cname = loc.get('Cluster_Name') or loc.get('District') or ''
                    if loc_id:
                        loc_map[loc_id] = cname.strip()
            
            for fran in col_franchise.find():
                fid = fran.get('franchise_id')
                fname = fran.get('franchise_name') or fid
                cluster = loc_map.get(fran.get('location_id'), '')
                display_name = f"{fname} ({cluster})".strip() if cluster else fname
                if fid:
                    name_map[fid] = display_name
    except Exception as e:
        print("Error getting franchise name map:", e)
    return name_map

def format_date(dt):
    if not dt:
        return None
    if isinstance(dt, datetime.datetime) or isinstance(dt, datetime.date):
        return dt.isoformat()
    return str(dt)

@api_view(['GET', 'POST'])
def home_collections(request):
    col = get_mongo_collection('franchise_homecollection')
    if col is None:
        return Response({"error": "Database connection failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if request.method == 'GET':
        franchise_id = request.query_params.get('franchise_id')
        status_param = request.query_params.get('status')
        date_param = request.query_params.get('date')
        from_date = request.query_params.get('from_date') or date_param
        to_date = request.query_params.get('to_date') or date_param
        search = request.query_params.get('search', '').strip()

        mongo_query = {}

        if franchise_id:
            mongo_query['franchise_id'] = franchise_id

        if status_param:
            mongo_query['status'] = status_param

        # Date range filtering on 'date' or 'created_date'
        if from_date or to_date:
            date_filter = {}
            if from_date:
                try:
                    f_dt = datetime.datetime.strptime(from_date, '%Y-%m-%d')
                    date_filter['$gte'] = f_dt
                except Exception:
                    pass
            if to_date:
                try:
                    t_dt = datetime.datetime.strptime(to_date, '%Y-%m-%d') + datetime.timedelta(days=1, microseconds=-1)
                    date_filter['$lte'] = t_dt
                except Exception:
                    pass
            if date_filter:
                mongo_query['$or'] = [
                    {'date': date_filter},
                    {'created_date': date_filter}
                ]

        docs = list(col.find(mongo_query).sort('created_date', -1))
        franchise_name_map = get_franchise_name_map()

        results = []
        for d in docs:
            fid = d.get('franchise_id', '')
            fname = franchise_name_map.get(fid, fid)
            
            p_name = d.get('patient_name', '')
            addr = d.get('address', '')
            ph = d.get('phone', '')

            # Search in-memory if requested
            if search:
                s_lower = search.lower()
                if (s_lower not in p_name.lower() and 
                    s_lower not in addr.lower() and 
                    s_lower not in ph.lower() and 
                    s_lower not in fid.lower()):
                    continue

            results.append({
                "id": str(d.get('_id')),
                "patient_name": p_name,
                "address": addr,
                "phone": ph,
                "franchise_id": fid,
                "franchise_name": fname,
                "status": d.get('status', 'Assigned'),
                "date": format_date(d.get('date') or d.get('created_date')),
                "created_date": format_date(d.get('created_date')),
                "created_by": d.get('created_by', ''),
                "lastmodified_date": format_date(d.get('lastmodified_date')),
                "lastmodified_by": d.get('lastmodified_by', ''),
                "accepted_by": d.get('accepted_by', ''),
                "sample_accepted_time": format_date(d.get('sample_accepted_time')),
                "Remarks": d.get('Remarks') if 'Remarks' in d else d.get('remarks', ''),
            })

        return Response(results, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        # Create Home Collection task
        data = request.data
        patient_name = data.get('patient_name', '').strip()
        address = data.get('address', '').strip()
        phone = data.get('phone', '').strip()
        franchise_id = data.get('franchise_id', '').strip()
        created_by = data.get('created_by', 'system')
        remarks = data.get('Remarks') if 'Remarks' in data else data.get('remarks', '')
        now = datetime.datetime.now()

        doc = {
            "patient_name": patient_name,
            "address": address,
            "phone": phone,
            "franchise_id": franchise_id,
            "created_by": created_by,
            "created_date": now,
            "lastmodified_by": None,
            "lastmodified_date": now,
            "status": "Assigned",
            "date": now,
            "Remarks": remarks
        }

        res = col.insert_one(doc)
        doc['id'] = str(res.inserted_id)
        doc['_id'] = str(res.inserted_id)
        doc['created_date'] = format_date(now)
        doc['lastmodified_date'] = format_date(now)
        doc['date'] = format_date(now)

        return Response(doc, status=status.HTTP_201_CREATED)

@api_view(['PATCH', 'PUT'])
def accept_home_collection(request, collection_id):
    col = get_mongo_collection('franchise_homecollection')
    if col is None:
        return Response({"error": "Database connection failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        obj_id = ObjectId(collection_id)
    except Exception:
        return Response({"error": "Invalid collection ID"}, status=status.HTTP_400_BAD_REQUEST)

    doc = col.find_one({"_id": obj_id})
    if not doc:
        return Response({"error": "Home collection task not found"}, status=status.HTTP_404_NOT_FOUND)

    payload = request.data or {}
    franchise_id = payload.get('franchise_id') or doc.get('franchise_id') or 'SHF004'
    user_id = payload.get('accepted_by') or payload.get('user_id') or franchise_id
    remarks = payload.get('Remarks') if 'Remarks' in payload else payload.get('remarks', '')
    new_status = payload.get('status')

    now = datetime.datetime.now()
    update_fields = {
        "lastmodified_by": user_id,
        "lastmodified_date": now,
        "Remarks": remarks
    }

    if new_status == 'Accepted':
        update_fields["status"] = "Accepted"
        update_fields["accepted_by"] = user_id
        update_fields["sample_accepted_time"] = now
    elif new_status:
        update_fields["status"] = new_status

    col.update_one({"_id": obj_id}, {"$set": update_fields})

    updated_doc = col.find_one({"_id": obj_id})

    return Response({
        "message": "Home collection updated successfully",
        "id": collection_id,
        "status": updated_doc.get('status', 'Assigned'),
        "lastmodified_date": format_date(now),
        "lastmodified_by": user_id,
        "accepted_by": updated_doc.get('accepted_by', ''),
        "sample_accepted_time": format_date(updated_doc.get('sample_accepted_time')),
        "Remarks": updated_doc.get('Remarks') or ''
    }, status=status.HTTP_200_OK)
