from django.urls import path
from . import views 
from .Payment import payment_views
urlpatterns = [
    path('search-patient/', views.search_patient, name='search_patient'),
    path('registerpatientdetails/', views.register_patient, name='register_patient'),
    path('test-details/', views.get_test_details, name='get_test_details'),
    path('getactivelocations/', views.get_active_franchise_locations, name='get_active_franchise_locations'),
    path('patientslist/', views.patient_list_by_date, name='patient_list_by_date'),
    path('patients/<str:patient_id>/', views.get_patient_by_id, name='get_patient_by_id'),
    path('allpatients/', views.get_all_patients,name='get_all_patients'),
    path('updatepatient/<str:pk>/', views.update_patient,name='update_patient'),
    path('login/', views.login_view, name='login'),
    path('update_barcode_status/<str:barcode_id>/', views.update_barcode_status, name='update_barcode_status'),
    path('get_patient_by_franchise_and_date/', views.get_patient_by_franchise_and_date, name='get_patient_by_franchise_and_date'),
    path('sample/', views.sample, name='sample'),
    path('samples/transferred/', views.get_transferred_samples, name='get_transferred_samples'),
    path('batch/', views.batch_generation, name='batch_generation'),
    path('wallet-balance/<str:franchise_id>/', payment_views.get_wallet_balance, name='wallet_balance'),
    path('payment-history/<str:franchise_id>/', payment_views.get_payment_history, name='payment_history'),
    path('save-payment/', payment_views.save_payment, name='save_payment'),
    path('add-wallet-balance/', payment_views.add_wallet_balance, name='add_wallet_balance'),
    path('currencies/', payment_views.get_currencies, name='get_currencies'),
    path('payment-gateways/', payment_views.get_payment_gateways, name='get_payment_gateways'),
    path('check-barcode-exists/', views.check_barcode_exists, name='check_barcode_exists'),
    path('registrations/', views.get_registrations_by_franchise_and_date, name='get_registrations_by_franchise_and_date'),
    path('get_test_values/', views.get_test_values, name='get_test_values'),
    path('get_patient_by_barcode/', views.get_patient_by_barcode, name='get_patient_by_barcode')
]
