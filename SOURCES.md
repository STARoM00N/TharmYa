# แหล่งข้อมูลของฐานข้อมูลยา (`thai_otc_drugs.json`)

> ฐานข้อมูลยาในไฟล์ `thai_otc_drugs.json` (v2.0) สังเคราะห์ขึ้นจากแหล่งข้อมูลทางการของไทยและสากล โดยมีจุดประสงค์เพื่อใช้ในระบบ Retrieval-Augmented Generation (RAG) ของ TharmYa AI — ไม่ใช่คำแนะนำทางการแพทย์

**สรุปสถานะ**
- จำนวนยาทั้งหมด: **52 รายการ** (เดิม 25 + เพิ่มใหม่ 27 จากรายการ ยาสามัญประจำบ้านแผนปัจจุบัน ฉบับ สธ.)
- วันที่อัปเดตล่าสุด: **2026-05-15**
- เวอร์ชั่นไฟล์: `metadata.version = "2.0"`

---

## 1. แหล่งข้อมูลหลัก (Primary Sources)

### 1.1 ประกาศกระทรวงสาธารณสุข เรื่อง ยาสามัญประจำบ้านแผนปัจจุบัน

- **ฉบับ**: ฉบับที่ ๓ พ.ศ. ๒๕๕๐ (รายการ 52 รายการ)
- **สถานะ**: เอกสารกฎหมาย (ราชกิจจานุเบกษา) — ใช้อ้างอิงเป็นทางการ
- **เอกสารที่ใช้**: รายการสรุป 52 รายการ จาก สสจ. สมุทรปราการ
- **URL**: <https://fdasamutprakan.com/wp-content/uploads/2014/08/รายการยาสามัญประจำบ้าน.pdf> (ดาวน์โหลดเมื่อ 2026-05-15)
- **ราชกิจจานุเบกษา ฉบับเดิม**: <https://www.ratchakitcha.soc.go.th/DATA/PDF/2562/E/175/T_0010.PDF>
- **ใช้กับ entry**: OTC026–OTC052 (และ cross-reference กับ OTC001–OTC025 เดิม)
- **ข้อมูลที่ดึงโดยตรง**: ชื่อยาภาษาไทย, สูตรตำรับ, สรรพคุณ, ขนาดและวิธีใช้, คำเตือน, การเก็บรักษา, ขนาดบรรจุ

### 1.2 บัญชียาหลักแห่งชาติ (National List of Essential Medicines)

- **ฉบับ**: NLEM 2026 (Thailand) — WHO publication
- **URL**: <https://www.who.int/publications/m/item/thailand--national-list-of-essential-medicines-(nlem)-(thai)>
- **PDF download (9.6 MB)**: [thailand_neml_2026.pdf](https://cdn.who.int/media/docs/default-source/essential-medicines/national-essential-medicines-lists-(neml)/searo_neml/thailand_neml_2026.pdf)
- **ใช้กับ**: cross-check ขนาดยาที่ใช้ในผู้ใหญ่และเด็ก, ข้อบ่งใช้ทางการ

### 1.3 Thai Medicines Terminology (TMT)

- **องค์กร**: สำนักพัฒนามาตรฐานระบบข้อมูลสุขภาพไทย (สมสท. / THIS Center)
- **URL Portal**: <https://this.or.th/service/tmt/>
- **Open Data**: <https://data.go.th/dataset/thai-medicines-terminology-tmt>
- **License**: Creative Commons Attribution
- **ใช้กับ**: อ้างอิงชื่อสามัญ (Generic name) มาตรฐาน, รหัสยาสากล (mapping ในอนาคต)
- **หมายเหตุ**: ในเวอร์ชั่น 2.0 ของ `thai_otc_drugs.json` ยังไม่ได้ฝัง TMT code โดยตรง — แผนงานในอนาคต

### 1.4 National Drug Information (NDI) — สำนักงานคณะกรรมการอาหารและยา

- **URL**: <https://ndi.fda.moph.go.th/>
- **ใช้กับ**: ตรวจสอบทะเบียนยาและชื่อการค้าที่จดทะเบียนในไทย (~14,832 รายการ)
- **ข้อจำกัด**: ค้นผ่านหน้าเว็บเท่านั้น — ไม่มี Open API

### 1.5 ข้อมูลเสริม (Brand names + price ranges)

- ชื่อการค้า (`common_brands`) และช่วงราคา (`price_range_thb`) เก็บจาก:
  - ฐานข้อมูลร้านขายยาในไทย (ราคาตลาดปี 2025–2026)
  - MIMS Thailand — <https://www.mims.com/thailand>
  - ความรู้ผู้ใช้ทั่วไป (เช่น ยาดมโป๊ยเซียน, ยาหม่องตราเสือ, ทิงเจอร์มหาหิงคุ์ตราใบโพธิ์)
- **หมายเหตุ**: ช่วงราคา = ราคาประมาณการต่อแพ็คปกติในร้านขายยาทั่วไป (ไม่ใช่ราคาขายปลีกอย่างเป็นทางการ)

### 1.6 ข้อมูล Drug Interactions และ Warnings

- **Drugs.com Interaction Checker**: <https://www.drugs.com/drug_interactions.html>
- **Lexicomp / Micromedex** (ใช้อ้างอิงระหว่างจัดทำ)
- **ตำราเภสัชวิทยาคลินิก** (Goodman & Gilman, Katzung)
- **ใช้กับ**: ฟิลด์ `drug_interactions`, `warnings`, `contraindications`, `should_see_doctor_if`

---

## 2. การ Map ข้อมูลทางการเข้าสู่ schema ของ project

ข้อมูลทางการในประกาศ สธ. มี field ไม่ตรงกับ schema เดิมของ project — ทำการ map ดังนี้:

| ฟิลด์ใน `thai_otc_drugs.json` | ที่มา (จากประกาศ สธ.) |
|---|---|
| `name_thai` | คอลัมน์ "รายการ" |
| `name_generic` | สังเคราะห์จาก "สูตรตำรับ" + standard generic name |
| `symptoms_treated` | คอลัมน์ "สรรพคุณ" + ขยายด้วยอาการที่พบบ่อย |
| `dosage.adult`, `dosage.child` | คอลัมน์ "ขนาดและวิธีใช้" |
| `warnings` | คอลัมน์ "คำเตือน" + คำเตือน drug interaction เสริม |
| `contraindications` | สกัดจาก "คำเตือน" ที่ระบุ "ห้ามใช้ในผู้ที่เป็น..." |
| `common_brands`, `price_range_thb` | ข้อมูลตลาด — ไม่อยู่ในประกาศ สธ. (ใช้ MIMS + ความรู้ทั่วไป) |
| `should_see_doctor_if` | สกัดจาก red-flag clauses ในคำเตือน + ดุลพินิจคลินิกทั่วไป |
| `otc_available` | True เสมอ (เนื่องจากเป็นรายการในประกาศ ยาสามัญประจำบ้าน) |

---

## 3. รายการยาที่เพิ่มในเวอร์ชั่น 2.0 (OTC026–OTC052)

| ID | ยา (ไทย) | อ้างอิงรายการ สธ. |
|---|---|---|
| OTC026 | ยาถ่ายพยาธิตัวกลม (Mebendazole) | รายการที่ 14 |
| OTC027 | ยาเม็ดแก้เมารถ (Dimenhydrinate) | รายการที่ 25 |
| OTC028 | ยาหยอดตา Sulfacetamide 10% | รายการที่ 26 |
| OTC029 | ยาล้างตา (NaCl 0.9%) | รายการที่ 27 |
| OTC030 | ยากวาดคอ Povidone-Iodine | รายการที่ 28 |
| OTC031 | ยารักษาลิ้นเป็นฝ้า (Gentian Violet) | รายการที่ 29 |
| OTC032 | ยาแก้ปวดฟัน (น้ำมันกานพลู) | รายการที่ 30 |
| OTC033 | ยาอมบรรเทาเจ็บคอ (Amyl metacresol) | รายการที่ 32 |
| OTC034 | ครีมรักษาแผลไฟไหม้ Silver Sulfadiazine | รายการที่ 39 |
| OTC035 | ยาทาระเหยบรรเทาคัดจมูก | รายการที่ 24 |
| OTC036 | เหล้าแอมโมเนียหอม (ยาดม) | รายการที่ 22 |
| OTC037 | ยาดมเมนทอล/สมุนไพร | รายการที่ 23 |
| OTC038 | ยาหม่อง (Methyl Salicylate + Menthol) | รายการที่ 40 |
| OTC039 | ยารักษาหิดเหา Benzyl Benzoate | รายการที่ 41 |
| OTC040 | Whitfield's Ointment (น้ำกัดเท้า/กลาก) | รายการที่ 43 |
| OTC041 | ยาทาคาลาไมน์ (Calamine) | รายการที่ 45 |
| OTC042 | วิตามินบีรวม | รายการที่ 47 |
| OTC043 | Ferrous Sulfate (บำรุงโลหิต) | รายการที่ 49 |
| OTC044 | วิตามินรวม (Multivitamin) | รายการที่ 50 |
| OTC045 | น้ำมันตับปลา (Cod Liver Oil) | รายการที่ 51–52 |
| OTC046 | ทิงเจอร์มหาหิงคุ์ | รายการที่ 7 |
| OTC047 | ยาเหน็บทวารกลีเซอรีน | รายการที่ 9–10 |
| OTC048 | พลาสเตอร์บรรเทาปวด | รายการที่ 18 |
| OTC049 | ยาอมระคายคอ (สมุนไพร) | รายการที่ 31 |
| OTC050 | ขี้ผึ้งกำมะถัน (รักษาหิด) | รายการที่ 42 |
| OTC051 | คอลทาร์ (Psoriasis) | รายการที่ 44 |
| OTC052 | โซเดียมไทโอซัลเฟต (เกลื้อน) | รายการที่ 46 |

---

## 4. รายการที่ "ไม่ได้" เพิ่มในไฟล์ JSON (เหตุผล)

ไม่ได้เพิ่มเพราะซ้ำกับ entry เดิม หรือไม่จำเป็นในบริบทผู้ใช้ปลายทาง:

| รายการ สธ. | เหตุผลที่ไม่เพิ่ม |
|---|---|
| #1–3, #5 ยา/น้ำลดกรด Al-Mg, ยาธาตุน้ำแดง | ครอบคลุมแล้วใน OTC010 (Antacid Al/Mg) |
| #4 ยาขับลม (Tincture) | สูตรเก่า — ไม่ใช่ยาที่ใช้บ่อยในปัจจุบัน |
| #6 ยาน้ำลดกรด NaHCO₃ (ทารก) | เฉพาะกลุ่ม ใช้น้อยในปัจจุบัน |
| #8 ผงน้ำตาลเกลือแร่ | ครอบคลุมแล้วใน OTC013 (ORS) |
| #11–12 ยาระบาย Mg/มะขามแขก | ครอบคลุมแล้วใน OTC014 (Bisacodyl/Senna) |
| #13 ยาสวนทวาร NaCl | ใช้น้อย — รวมไปยัง OTC047 (Glycerin) |
| #15–17 ยา Paracetamol | ครอบคลุมแล้วใน OTC001 |
| #19 Chlorpheniramine | ครอบคลุมแล้วใน OTC007 |
| #20 ยาน้ำแก้ไอเด็ก (Ammonium + Licorice) | ครอบคลุมแล้วใน OTC005 (Guaifenesin) |
| #21 ยาแก้ไอน้ำดำ (มี opium) | ไม่แนะนำ — เป็น OTC ที่ใช้น้อย |
| #33, #34, #36, #37, #38 ทิงเจอร์/แอลกอฮอล์ทำแผล | ครอบคลุมพอจากการมี OTC018 (Povidone-Iodine) — และ NaCl 0.9% ก็คือ OTC029 |
| #35 Povidone-Iodine ทำแผล | ครอบคลุมแล้วใน OTC018 |
| #48 Vitamin C | ครอบคลุมแล้วใน OTC019 |

---

## 5. สิ่งที่ AI ยัง "ไม่ได้รับประกัน" (Disclaimer)

1. **ขนาดยาแน่นอน**: ขนาดยาในไฟล์เป็นค่ามาตรฐานทั่วไป — กรณีเด็ก ผู้สูงอายุ หญิงตั้งครรภ์ และผู้มีโรคประจำตัวอาจต้องปรับ
2. **Drug interactions ครอบคลุมไม่ครบ**: เก็บเฉพาะที่พบบ่อยและมีนัยทางคลินิก — interaction รายตัวให้ค้นจาก [Drugs.com Interaction Checker](https://www.drugs.com/drug_interactions.html) หรือปรึกษาเภสัชกร
3. **ราคา**: เป็นค่าโดยประมาณ ไม่ใช่ราคา MRP หรือราคาขายปลีกที่ควบคุม
4. **ใช้ในการให้คำปรึกษาเบื้องต้นเท่านั้น**: ไม่ใช่การวินิจฉัยทางการแพทย์ — กรุณาปรึกษาเภสัชกรหรือแพทย์ก่อนใช้ยาทุกครั้ง

---

## 6. การปรับปรุงในอนาคต (Roadmap)

- [ ] ฝัง **TMT code (TPU)** ในแต่ละ entry สำหรับ interoperability กับระบบ HIS
- [ ] เพิ่ม **drug-drug interaction matrix** เป็น JSON แยก (มากกว่าฝังในแต่ละ entry)
- [ ] ดึงข้อมูล `ยาสามัญประจำบ้านแผนโบราณ` ([dmsic.moph.go.th](https://dmsic.moph.go.th/index/detail/496)) เพิ่ม
- [ ] เพิ่ม Drug Image จาก [NDI FDA](https://ndi.fda.moph.go.th/) (ต้องขออนุญาต)
- [ ] Cross-link กับ **NLEM 2026** เพื่อระบุยาที่อยู่ในบัญชียาหลักแห่งชาติ

---

## 7. License & Attribution

- ข้อมูลในไฟล์ `thai_otc_drugs.json` รวบรวมจากแหล่งข้อมูลสาธารณะของรัฐบาลไทยที่เผยแพร่ตามกฎหมาย
- **Primary source** (ประกาศ สธ. ยาสามัญประจำบ้าน): เอกสารกฎหมายเปิดเสรี (public document)
- **TMT**: Creative Commons Attribution
- **NLEM 2026**: WHO published — ไม่มี restriction สำหรับการใช้ทางวิชาการ
- ข้อมูลเสริม (ชื่อการค้า, ราคา): ใช้เพื่อการศึกษา ไม่ใช่ commercial endorsement
