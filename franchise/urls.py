from django.urls import path
from . import views 

urlpatterns = [
    path('franchiseregister/', views.register_franchise, name='register_franchise'),
    path('franchise/reset-password/', views.reset_franchise_password, name='reset_franchise_password'),
    path('franchise/validate-token/', views.validate_reset_token, name='validate_reset_token'),
    path('toggle-franchise-status/<str:franchise_id>/', views.toggle_franchise_status),#employee toggle
    path('getlocations/', views.get_all_franchise_locations, name='get_all_franchise_locations'),#toggle
    path('getactivelocations/', views.get_inactive_franchise_locations, name='get_active_franchise_locations'),#dropdown
    path('get-franchise/', views.get_registered_franchise, name='get_registered_franchise'),
    path('get-file/<str:file_id>/', views.get_file, name='get_file'),
    path('updatestatus/<str:location_id>/', views.update_franchise_status, name='update_franchise_status'),
    path('get-franchise-edit/<str:franchise_id>/', views.get_franchise, name='get_franchise'),
    path('update-franchise/<str:franchise_id>/', views.update_franchise, name='update_franchise'),
    path('getnextfranchiseid/', views.generate_next_franchise_id, name='generate_next_franchise_id'),
    path('get_all_barcodes/', views.get_all_barcodes, name='get_all_barcodes'),
    path('getfranchise/', views.get_franchises, name='get_franchises'),
    path('stockbarcode/', views.savestockbarcode, name='savestockbarcode'),
    path('update_barcode_status/<str:barcode_id>/', views.update_barcode_status, name='update_barcode_status'),
    path('inactive-franchises/', views.inactive_franchises, name='inactive-franchises'),
    path('resend-password-reset/', views.resend_password_reset_email, name='resend_password_reset'),
    path('bulk-resend-password-reset/', views.bulk_resend_password_reset_emails, name='bulk_resend_password_reset'),
    path('cancel-requested/', views.get_cancel_requested_tests, name='cancel-requested'),
    path('update-test-status/', views.update_test_status, name='update_test_status'),
    path('update_cancel_status/', views.update_cancel_status, name='update_cancel_status'),

    
]
