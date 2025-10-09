

PAGE_MAPPING = {
    
    '/_b_a_c_k_e_n_d/franchise/franchiseregister/': 'FE-P-FR',
    '/_b_a_c_k_e_n_d/franchise/franchise/reset-password/':'FE-P-FRP', 
    '/_b_a_c_k_e_n_d/franchise/franchise/franchise/validate-token/':'FE-P-FVT',
    '/_b_a_c_k_e_n_d/franchise/toggle-franchise-status/.*/': 'FE-P-FS',
    '/_b_a_c_k_e_n_d/franchise/getlocations/': 'FE-P-FGL',
    '/_b_a_c_k_e_n_d/franchise/getactivelocations/': 'FE-P-FAL',
    '/_b_a_c_k_e_n_d/franchise/get-franchise/': 'FE-P-FG',
    '/_b_a_c_k_e_n_d/franchise/get-file/.*/': 'FE-P-FGF',
    '/_b_a_c_k_e_n_d/franchise/updatestatus/.*/': 'FE-P-FUS',
    '/_b_a_c_k_e_n_d/franchise/get-franchise-edit/.*/': 'FE-P-FGE',
    '/_b_a_c_k_e_n_d/franchise/update-franchise/.*':'FE-P-FF',
    '/_b_a_c_k_e_n_d/franchise/getnextfranchiseid/':'FE-P-FGFID',
    '/_b_a_c_k_e_n_d/franchise/savebarcode/':'FE-P-FSB',
    '/_b_a_c_k_e_n_d/franchise/update_barcode_status/.*/':'FE-P-FGL',
    '/_b_a_c_k_e_n_d/franchise/get_all_barcodes/':'FE-P-FGL',
    '/_b_a_c_k_e_n_d/franchise/getfranchise/':'FE-P-FGF',
    '/_b_a_c_k_e_n_d/franchise/stockbarcode/':'FE-P-FR',
    '/_b_a_c_k_e_n_d/franchise/update_barcode_status/.*/':'FE-P-FUBS',

    'franchiseregister/': 'FE-P-FR',
    'toggle-franchise-status/.*/': 'FE-P-FS',
    'getlocations/': 'FE-P-FGL',
    'getactivelocations/': 'FE-P-FAL',
    'get-franchise/': 'FE-P-FF',
    'get-file/<str:file_id>/': 'FE-P-FUS',
    'updatestatus/.*/':'FE-P-FUS',
    'get-franchise-edit/.*/': 'FE-P-FGF',
    'update-franchise/.*/':'FE-P-FF',
    'savebarcode/':'FE-P-FSB',
    'update_barcode_status/':'FE-P-FUB',
    'getnextfranchiseid/':'FE-P-FGFID',
    'update_barcode_status/':'FE-P-FUBS',
}

PAGE_ACTION_MAPPING = {
    'xxx': {
        'DELETE':'RWD',
    },
}

GEN_ACTION_MAPPING = {
    'POST': 'RW',
    'PUT': 'RW',
    'DELETE': 'RW',
    'GET': 'R',
    'PATCH':'RW'
}