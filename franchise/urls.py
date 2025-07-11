from django.urls import path
from . import views 

urlpatterns = [
    path('search-patient/', views.search_patient, name='search_patient'),
    path('registerpatientdetails/', views.register_patient, name='register_patient'),
    path('test-details/', views.get_test_details, name='get_test_details'),
    # path('patientdetails/', views.patientdetails, name='patientdetails'),
    path('patientslist/', views.patient_list_by_date, name='patient_list_by_date'),
    path('patients/<str:patient_id>/', views.get_patient_by_id, name='get_patient_by_id'),
    path('allpatients/', views.get_all_patients,name='get_all_patients'),
    path('updatepatient/<str:pk>/', views.update_patient,name='update_patient'),
    path('savebarcode/', views.save_barcode,name='update_patient'),
    path('login/', views.login_view, name='login'),
    path('save-payment/', views.SavePaymentView.as_view(), name='save_payment'),
    path('add-wallet-balance/', views.AddWalletBalanceView.as_view(), name='add_wallet_balance'),
    path('wallet-balance/<str:franchise_id>/', views.WalletBalanceView.as_view(), name='wallet_balance'),
    path('payment-history/<str:franchise_id>/', views.PaymentHistoryView.as_view(), name='payment_history'),
]
