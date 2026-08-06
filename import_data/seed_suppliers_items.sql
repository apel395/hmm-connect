BEGIN;

INSERT INTO item_groups (code,name,is_active,created_at,updated_at)
VALUES
('1','FOOD',TRUE,NOW(),NOW()),
('2','BEVERAGE',TRUE,NOW(),NOW()),
('3','MATERIAL',TRUE,NOW(),NOW())
ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name,is_active=TRUE,updated_at=NOW();

INSERT INTO item_subgroups (code,name,group_id,is_active,created_at,updated_at)
SELECT v.code,v.name,g.id,TRUE,NOW(),NOW()
FROM (VALUES
('1-1','MEAT','1'),
('1-2','POULTRY','1'),
('1-3','FISH','1'),
('1-8','GRESORIS','1'),
('1-9','SNACK','1'),
('2-3','BEER','2'),
('3-1','GUEST SUPPLIES','3'),
('3-4','STATIONARY','3')
) AS v(code,name,group_code)
JOIN item_groups g ON g.code=v.group_code
ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name,group_id=EXCLUDED.group_id,is_active=TRUE,updated_at=NOW();

INSERT INTO products (
code,name,group_code,group_name,subgroup_code,subgroup_name,uom,usage_uom,conversion,
description,cost_price,selling_price,minimum_stock,reorder_level,maximum_stock,lead_time_days,is_active,created_at,updated_at)
VALUES
('1-100001','Daging Khas Dalam','1','FOOD','1-1','MEAT','Kg','Gram',1000,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-200001','Daging Ayam Whole','1','FOOD','1-2','POULTRY','Kg','Gram',1000,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-200002','Dada Ayam','1','FOOD','1-2','POULTRY','Kg','Gram',1000,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-300001','Ikan Dori','1','FOOD','1-3','FISH','Kg','Gram',1000,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('3-400001','Kertas HVS A4 70 gr','3','MATERIAL','3-4','STATIONARY','Rim','Rim',1,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('3-100001','Tissue Napkin','3','MATERIAL','3-1','GUEST SUPPLIES','Pack','Pack',1,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('2-300001','Bir Bintang','2','BEVERAGE','2-3','BEER','Can','Can',1,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-900001','Lemper','1','FOOD','1-9','SNACK','Pcs','Gram',1,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-800001','Garam Dolphin 250 Gr','1','FOOD','1-8','GRESORIS','Bks','Gram',250,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-900002','Peyek','1','FOOD','1-9','SNACK','Kg','Kg',1,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW()),
('1-300002','Ikan Tuna','1','FOOD','1-3','FISH','kg','kg',1,NULL,0,0,0,0,0,0,TRUE,NOW(),NOW())
ON CONFLICT (code) DO UPDATE SET
name=EXCLUDED.name,group_code=EXCLUDED.group_code,group_name=EXCLUDED.group_name,
subgroup_code=EXCLUDED.subgroup_code,subgroup_name=EXCLUDED.subgroup_name,
uom=EXCLUDED.uom,usage_uom=EXCLUDED.usage_uom,conversion=EXCLUDED.conversion,
is_active=TRUE,updated_at=NOW();

INSERT INTO suppliers (
code,name,address,bank_name,bank_account_number,bank_account_name,is_active,created_at,updated_at)
VALUES
('PT0001','PT. RIZANINDO ANDASATA PRIMA','Jl. Yos Sudarso No. 12A, Pekanbaru, 28154',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PT0002','PT. SUKANDA DJAYA','Jl. Siak Palas II Simbang Bingung Rumbai Bukit, Pekanbaru, 28264',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('CV0001','CV. FALIQ ADIRA','Jl. Dewi Sartika Kel. Duri Barat, Duri, 28783',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('UD0001','UD. HASIL LAUT','Jl. Sudirman, 28112',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PT0003','PT. HARVITA TISI MULIA','Jl. Tanjung Jati No. 07, Pekanbaru, 28291',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PT0004','PT. TIRTA SUMBER MEKARSARI','Jl. Siak II KM 12 Palas, Pekanbaru, 28265',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('CV0002','CV. MITRA LANGGENG','Jl. Harjosari Sukajadi, 28156',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('CV0003','CV. IKA CATERING','Jl. Hasanudding gang Abidin II, Pekanbaru, 28125',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0001','AYAM GORENG SUHARTI','Jl. Riau No 38-40, Pekanbaru, 28292',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PT0005','PT. DINAMIKA CITRA RASA','Jl. Jend Sudirman No. 389B wonorejo Kec Marpoyan Damai, Pekanbaru, 28128',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0002','RESTORAN APOLLO','Jl. Gatot Subroto No 30-32, Pekanbaru, 28155',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('UD0002','UD. UMAR BERKAH','Jl. Uka Garuda Sakti, Pekanbaru, 28291',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0003','EVI MALINDA','Bandar Pedada RT/RW 006/003 Sabak Auh Kab. Siak, Siak, 28685',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0004','PEMPEK WENNY','JL SEKOLAH NO 170',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0005','DIMSUM LEKER','PARKVILLE D01 RUMBAI',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0006','KOTA BUANA','JL HOS COKROAMINOTO',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0007','SIOMAY UNYIL','JL GATOT SUBROTO',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0008','ROTI JALAH DAN REMPEYEK','JL MULIYA JAYA NO 14',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0009','RM KHAS MELAYU','JL ADI SUCIPTO',NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0010','SLAMET SUPRIYANTO','Jl. Yos Sudarso RT 10 Sarijaya, Sangasanga','BNI','0394308957','Slamet Supriyanto',TRUE,NOW(),NOW()),
('PR0011','PUGUH WIBOWO','Jl. Slamet Riadi No. 3, Bantuas, Kec. Sangasanga, Kab. Kutai Kartanegara, Kalimantan Timur','BNI','1719269958','Puguh Wibowo',TRUE,NOW(),NOW()),
('PR0012','SUWARNO-KAFKA MART','Jalan Mada Sanga Sanga Dalam, Kab. Kutai Kartanegara, Kalimantan Timur 75254','Mandiri','1480012294677','Suwarno',TRUE,NOW(),NOW()),
('PR0013','HIKMAH NKL','Jalan Provinsi RT 04 Pasar Subuh Makroman, Kota Samarinda, Kalimantan Timur','BNI','1173677330','Hikmah',TRUE,NOW(),NOW()),
('PR0014','AIR MINERAL DC',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0015','RUSDIANA','Danau Samboja RT 06, Kel. Sungai Seluang, Kec. Samboja','BRI','447801016862538','Rusdiana',TRUE,NOW(),NOW()),
('PR0016','SNACK RENNY',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0017','RM. PADANG MINANG ASLI',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0018','SNACK KANA''S',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0019','SNACK ERA',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0020','SNACK BARAS',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PR0021','TPS CLUB GALON','Jl. Projakal, Kelurahan Batu Ampat, Kecamatan Balikpapan Utara 76127','BCA','3193077109','PT. Indomarco Adi Prima',TRUE,NOW(),NOW()),
('PR0022','PEST CONTROL',NULL,NULL,NULL,NULL,TRUE,NOW(),NOW()),
('PT0006','PT. LISTY HARJO MAKMUR','Jl. Mangga I/E 172 Pondok Chandra, Surabaya','Mandiri','1420033322255','PT. Listy Harjo Makmur',TRUE,NOW(),NOW()),
('CV0004','CV. AMANAH TRIUTAMA','Jl. Siaga Dalam No. 209 RT 17, Balikpapan Kota','Mandiri','1490004796308','Safaruddin Asri',TRUE,NOW(),NOW()),
('PT0007','PT. RENTOKIL INDONESIA','Jl. MT Haryono RT 43 No. 6A, Kel. Graha Indah, Kec. Balikpapan Utara, Balikpapan','Mandiri','88611700065045','PT. Rentokil Indonesia',TRUE,NOW(),NOW()),
('CV0005','CV RIA','Jl. Pandan Sari No. 80 RT 022, Kel. Marga Sari, Kec. Balikpapan Barat, Balikpapan 76131','Mandiri','1490016652820','CV Ria',TRUE,NOW(),NOW()),
('PR0024','BU ERNI / ACE MART','Jl. Merbabu No. 27, Samarinda','BCA','0278002899','Erny Sulistio',TRUE,NOW(),NOW()),
('CV0006','CV BATAM PROVISION SERVICES','Pasar Puja Bahari Kios Blok B 13-15, Lubuk Baja, Kota Batam','Mandiri','1090015566557','CV Batam Provision Services',TRUE,NOW(),NOW()),
('PT0008','PT KHARISMA KARYA KARTIKA','Jl. Budi Kemuliaan, Blok PH No. 90, Kampung Seraya, Batam','BCA','617181111','PT Kharisma Karya Kartika',TRUE,NOW(),NOW()),
('PT0009','REZEKINDO MAKMUR SENTOSA','Komp. Nagoya Newton, Blok E No. 1 dan 2 RT 01 RW 08, Lubuk Baja, Kota Batam','BCA','8520491199','Rezekindo Makmur Sentosa',TRUE,NOW(),NOW())
ON CONFLICT (code) DO UPDATE SET
name=EXCLUDED.name,
address=COALESCE(EXCLUDED.address,suppliers.address),
bank_name=COALESCE(EXCLUDED.bank_name,suppliers.bank_name),
bank_account_number=COALESCE(EXCLUDED.bank_account_number,suppliers.bank_account_number),
bank_account_name=COALESCE(EXCLUDED.bank_account_name,suppliers.bank_account_name),
is_active=TRUE,updated_at=NOW();

INSERT INTO supplier_rows (supplier_id,pic_name,phone,unit,item)
SELECT s.id,v.pic_name,v.phone,v.unit,v.item
FROM (VALUES
('PT0001',NULL,'0761-31272',NULL,NULL),
('PT0002',NULL,'0761-864500',NULL,NULL),
('CV0001',NULL,'0765-93227',NULL,NULL),
('UD0001',NULL,'8126868421',NULL,NULL),
('PT0003',NULL,'0761-25644',NULL,NULL),
('PT0004',NULL,'0761-7877633',NULL,NULL),
('CV0002',NULL,'0761-37249',NULL,NULL),
('CV0003',NULL,'0812-666-59089',NULL,NULL),
('PR0001',NULL,'0761-21635',NULL,NULL),
('PT0005',NULL,'0761-7892016',NULL,NULL),
('PR0002',NULL,'0761-35234',NULL,NULL),
('UD0002',NULL,'81371320647',NULL,NULL),
('PR0003',NULL,'0813-7183-6622',NULL,NULL),
('PR0004',NULL,'82244819998',NULL,NULL),
('PR0005',NULL,'81362468257',NULL,NULL),
('PR0006',NULL,'81371637743',NULL,NULL),
('PR0007',NULL,'82390442410',NULL,NULL),
('PR0008',NULL,'8127673296',NULL,NULL),
('PR0009',NULL,'8127581284',NULL,NULL),
('PR0010','Pak Supri','082223139359','PEP','Frozen (Ayam, Daging, Ikan)'),
('PR0011','Puguh','081222100388','PEP','Ayam, Vegetable, Fruit'),
('PR0012','Pak Warno','08125547253','PEP','Dry, Monouse, Beverage'),
('PR0013','Bu Hikmah','082255588009','PEP','All In'),
('PR0014',NULL,'82311013567',NULL,NULL),
('PR0015','Bu Ana','082153565199','PEP','Rumah Makan'),
('PR0016',NULL,'087812102204,',NULL,NULL),
('PR0017',NULL,'85247613208',NULL,NULL),
('PR0018',NULL,'81257418759',NULL,NULL),
('PR0019',NULL,'81253433680',NULL,NULL),
('PR0020',NULL,'85788606179',NULL,NULL),
('PR0021','Pak Ipan','082154736406','PHM','Air Gallon'),
('PR0022',NULL,'85750399343',NULL,NULL),
('PT0006','Bu Ima','081233912453','PHM','Dry, Monouse, Beverage dan Frozen (Ayam, Daging, Ikan)'),
('PT0006','BUK YUNITA','+62 895-7040-60556','SEPINGGAN & LAWE - LAWE','FROZEN, DRY, BEVERAGE, KITCHEN'),
('PT0006','BUK ARINDA','+62 815-4768-4712','PRCC','SUPPLIES, CLEANING MATERIAL'),
('PT0006',NULL,NULL,NULL,'VEGETABLE & FRUITS'),
('CV0004','Pak Capa','0811591345','PHM','Vegetable dan Fruit'),
('PT0007','Pak Fajar','085750399343','PHM','Hama'),
('CV0005','Pak Androw',NULL,'PHM','Meal Box'),
('PR0024','Bu Erny',NULL,'PEP','Air Gallon'),
('CV0006','Pak Yanto',NULL,'BATAM','Dry, Vegetable, Fruit'),
('PT0008','Bu Dewi',NULL,'BATAM','Frozen (Ayam, Daging, Ikan)'),
('PT0009','Ko Akeng',NULL,'BATAM','Fruit')
) AS v(code,pic_name,phone,unit,item)
JOIN suppliers s ON s.code=v.code
WHERE NOT EXISTS (
  SELECT 1 FROM supplier_rows r
  WHERE r.supplier_id=s.id
    AND COALESCE(r.pic_name,'')=COALESCE(v.pic_name,'')
    AND COALESCE(r.phone,'')=COALESCE(v.phone,'')
    AND COALESCE(r.unit,'')=COALESCE(v.unit,'')
    AND COALESCE(r.item,'')=COALESCE(v.item,'')
);

SELECT COUNT(*) AS item_count FROM products;
SELECT COUNT(*) AS supplier_count FROM suppliers;
COMMIT;
