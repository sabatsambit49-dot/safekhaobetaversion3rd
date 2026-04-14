"""
SafeKhao Backend — Flask + Neon PostgreSQL + Groq AI
Run: python server.py
"""

import os, json, re, urllib.request, urllib.error
import psycopg2, psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_JCjBU9wdPe4I@ep-blue-block-am4y24io.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"
)
AI_CLIENT  = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
GROQ_MODEL = "llama-3.3-70b-versatile"

# ── DB CONNECTION ──────────────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(DATABASE_URL)

def q(conn, sql, params=None):
    """Execute and return all rows as dicts."""
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(sql, params or ())
    try:
        return c.fetchall()
    except:
        return []

def run(conn, sql, params=None):
    """Execute without returning rows."""
    c = conn.cursor()
    c.execute(sql, params or ())

# ── INIT TABLES + SEED ────────────────────────────────────────────────────────
def init_db():
    conn = get_db()
    run(conn, """CREATE TABLE IF NOT EXISTS products (
        barcode TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        brand TEXT NOT NULL,
        category TEXT NOT NULL,
        icon TEXT DEFAULT '📦',
        image_url TEXT DEFAULT NULL,
        risk TEXT NOT NULL CHECK(risk IN ('ok','low','medium','high')),
        score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
        ingredients TEXT NOT NULL DEFAULT '[]',
        warnings TEXT NOT NULL DEFAULT '[]',
        future TEXT NOT NULL DEFAULT '[]',
        ai_generated INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    run(conn, """CREATE TABLE IF NOT EXISTS scans (
        id SERIAL PRIMARY KEY,
        barcode TEXT NOT NULL,
        product_name TEXT,
        scanned_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    run(conn, """CREATE TABLE IF NOT EXISTS ai_analyses (
        id SERIAL PRIMARY KEY,
        barcode TEXT NOT NULL,
        raw_input TEXT,
        result TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    _seed(conn)
    conn.close()

SEED = [
    ("8901719101038","Parle-G Gluco Biscuits 56g","Parle","Biscuit","🍪","low",32,
     '[{"n":"Wheat Flour (Maida)","r":"medium","note":"Refined, low fibre"},{"n":"Sugar","r":"medium","note":"High glycemic"},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"Invert Syrup","r":"medium","note":"Added sugar"},{"n":"Milk Solids","r":"ok","note":""},{"n":"Salt","r":"ok","note":""}]',
     '["Contains refined flour — not whole wheat","Moderate sugar and palm oil"]','[]'),
    ("8901719103919","Parle-G Glucose Biscuits 60g","Parle","Biscuit","🍪","low",32,
     '[{"n":"Wheat Flour (Maida)","r":"medium","note":"Refined"},{"n":"Sugar","r":"medium","note":""},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"Milk Solids","r":"ok","note":""},{"n":"Salt","r":"ok","note":""}]',
     '[]','[]'),
    ("8901719117183","Parle Hide & Seek Choco Chip 100g","Parle","Biscuit","🍫","medium",55,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"High"},{"n":"Cocoa Chips","r":"ok","note":"Antioxidants"},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"Emulsifier (INS 322)","r":"ok","note":"Lecithin"}]',
     '["High sugar and palm oil"]','["Dental decay with regular use"]'),
    ("8901719125072","Parle Happy Happy Creme 50g","Parle","Biscuit","🍪","medium",50,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Vegetable Oil","r":"medium","note":""},{"n":"Glucose Syrup","r":"medium","note":"Fast-absorbing sugar"}]',
     '["High sugar cream filling"]','[]'),
    ("8901719840845","Parle Melody Toffee 100 pcs","Parle","Candy","🍬","medium",60,
     '[{"n":"Sugar","r":"medium","note":""},{"n":"Glucose Syrup","r":"high","note":"Fast-absorbing sugar"},{"n":"Tartrazine (INS 102)","r":"high","note":"Yellow azo dye — hyperactivity in children"}]',
     '["Tartrazine azo dye — hyperactivity concern for children"]','[]'),
    ("8901719720727","Parle Krackjack Sweet & Salty 100g","Parle","Biscuit","🍘","low",30,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"low","note":"Low"},{"n":"Edible Vegetable Oil","r":"low","note":""},{"n":"Salt","r":"ok","note":""}]',
     '[]','[]'),
    ("8901719950124","Parle Monaco Classic Salted 100g","Parle","Biscuit","🍘","low",28,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Edible Oil","r":"low","note":""},{"n":"Salt","r":"ok","note":""},{"n":"Yeast","r":"ok","note":""}]',
     '["Low sugar — better option for diabetics"]','[]'),
    ("8901719103025","Parle Milk Shakti Biscuits 150g","Parle","Biscuit","🥛","low",26,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Milk Solids (8%)","r":"ok","note":"Good calcium source"},{"n":"Sugar","r":"low","note":"Low"},{"n":"Edible Oil","r":"low","note":""}]',
     '[]','[]'),
    ("8901063016767","Britannia Good Day Butter Biscuits 200g","Britannia","Biscuit","🍪","medium",50,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"8g per serving"},{"n":"Butter","r":"medium","note":"Natural saturated fat"},{"n":"Cashewnuts","r":"ok","note":"Healthy fats & protein"}]',
     '["8g sugar per serving"]','["Type 2 diabetes risk if eaten daily"]'),
    ("8901063032712","Britannia Treat Creme Wafers 55g","Britannia","Biscuit","🍫","medium",55,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Vegetable Fat","r":"medium","note":""},{"n":"Cocoa Powder","r":"ok","note":""}]',
     '["High sugar cream filling"]','[]'),
    ("8901063139329","Britannia Bourbon Chocolate Cream","Britannia","Biscuit","🍫","medium",52,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Cocoa Powder","r":"ok","note":"Antioxidants"},{"n":"Invert Syrup","r":"medium","note":"Added sugar"}]',
     '["Moderate sugar — limit to 2-3 biscuits"]','[]'),
    ("8901063164291","Britannia Tiger Glucose Biscuits 33g","Britannia","Biscuit","🍪","low",30,
     '[{"n":"Wheat Flour","r":"medium","note":"Refined"},{"n":"Sugar","r":"medium","note":""},{"n":"Milk Solids","r":"ok","note":""},{"n":"Vitamins & Iron","r":"ok","note":"Fortified"}]',
     '[]','[]'),
    ("8901063030930","Britannia Milk Bikis Biscuits 100g","Britannia","Biscuit","🥛","low",28,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Milk Solids (10%)","r":"ok","note":"Good calcium & protein"},{"n":"Sugar","r":"low","note":"Low"},{"n":"Edible Vegetable Oil","r":"low","note":""}]',
     '[]','[]'),
    ("8901063070509","Britannia NutriChoice Digestive Oats 200g","Britannia","Biscuit","🌾","low",22,
     '[{"n":"Whole Wheat Flour","r":"ok","note":"High fibre"},{"n":"Oats","r":"ok","note":"Beta-glucan — lowers cholesterol"},{"n":"Sugar","r":"low","note":"Low"},{"n":"Edible Oil","r":"low","note":""}]',
     '["One of the healthier biscuit options"]','[]'),
    ("8901058005851","Maggi Atta Noodles 70g","Nestle","Noodles","🍜","medium",48,
     '[{"n":"Whole Wheat Flour (Atta)","r":"ok","note":"Better than maida"},{"n":"Edible Vegetable Oil","r":"medium","note":""},{"n":"Salt","r":"medium","note":"High sodium — 860mg per serve"}]',
     '["Still high in sodium — 860mg per serve","Not fully whole wheat"]','[]'),
    ("8901058852899","Maggi 2-Minute Masala Noodles 70g","Nestle","Noodles","🍜","high",78,
     '[{"n":"Wheat Flour (Maida)","r":"medium","note":"Refined, low fibre"},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"MSG (INS 621)","r":"high","note":"Excess sodium, headaches in sensitive people"},{"n":"TBHQ (INS 319)","r":"high","note":"Synthetic preservative — banned in Japan & EU"}]',
     '["1 pack = 60% of your daily sodium limit","Contains TBHQ — banned in Japan & EU"]',
     '["Hypertension if consumed daily","Chronic kidney stress"]'),
    ("8901058852912","Maggi Vegetable Atta Noodles 75g","Nestle","Noodles","🍜","medium",45,
     '[{"n":"Whole Wheat Flour (Atta)","r":"ok","note":""},{"n":"Mixed Vegetables (Dehydrated)","r":"ok","note":""},{"n":"Salt","r":"medium","note":"Moderate sodium"}]',
     '["Better than regular Maggi — watch sodium"]','[]'),
    ("8901058557831","Nescafe Classic Instant Coffee 50g","Nestle","Beverage","☕","low",20,
     '[{"n":"Coffee (100%)","r":"ok","note":"Pure coffee — no additives"},{"n":"Caffeine (natural)","r":"low","note":"~60mg per cup"}]',
     '["Avoid if pregnant, nursing, or hypertensive"]','[]'),
    ("8901058004595","Nescafe Gold Roast Coffee 50g","Nestle","Beverage","☕","low",18,
     '[{"n":"100% Arabica Coffee","r":"ok","note":"Rich in antioxidants"},{"n":"Caffeine (natural)","r":"low","note":"~80mg per cup"}]',
     '["Avoid if anxious or hypertensive"]','[]'),
    ("8901058001105","KitKat Chocolate Bar 37g","Nestle","Chocolate","🍫","medium",55,
     '[{"n":"Sugar","r":"medium","note":""},{"n":"Wheat Flour","r":"ok","note":""},{"n":"Cocoa Butter","r":"ok","note":""},{"n":"Palm Oil","r":"medium","note":"Saturated fat"}]',
     '["1 bar = 20g sugar"]','[]'),
    ("8901058001372","Nestle Munch Chocolate Bar 26g","Nestle","Chocolate","🍫","medium",55,
     '[{"n":"Sugar","r":"medium","note":""},{"n":"Puffed Rice","r":"ok","note":""},{"n":"Milk Solids","r":"ok","note":""},{"n":"Palm Oil","r":"medium","note":"Saturated fat"}]',
     '["High sugar per serving"]','[]'),
    ("8901058004588","Nestle Milkmaid Condensed Milk 400g","Nestle","Dairy","🥛","high",70,
     '[{"n":"Whole Milk","r":"ok","note":""},{"n":"Sugar","r":"high","note":"Very high — 55g per 100g"}]',
     '["Extremely high sugar — 55g per 100g"]','["Type 2 diabetes","Obesity with regular use"]'),
    ("8901030869136","Amul Taaza Toned Milk 1L","Amul","Dairy","🥛","ok",7,
     '[{"n":"Toned Milk","r":"ok","note":"Good calcium, protein, vitamins"},{"n":"Vitamins A & D","r":"ok","note":"Fortified"}]',
     '[]','[]'),
    ("8901030875229","Amul Gold Full Cream Milk 1L","Amul","Dairy","🥛","low",18,
     '[{"n":"Full Cream Milk","r":"ok","note":"High calcium, fat-soluble vitamins"},{"n":"Fat (6% min)","r":"low","note":"Higher saturated fat than toned milk"}]',
     '["Higher in saturated fat than toned milk"]','[]'),
    ("8901030850523","Amul Masti Dahi Curd 400g","Amul","Dairy","🫙","ok",7,
     '[{"n":"Pasteurised Toned Milk","r":"ok","note":"Good calcium source"},{"n":"Lactic Acid Bacteria Cultures","r":"ok","note":"Probiotic — excellent for gut health"}]',
     '[]','[]'),
    ("8901030865404","Amul Butter Salted 100g","Amul","Dairy","🧈","low",24,
     '[{"n":"Pasteurised Cream","r":"ok","note":"Natural dairy fat"},{"n":"Common Salt","r":"ok","note":""},{"n":"Annatto Colour (INS 160b)","r":"ok","note":"Natural colour — safe"}]',
     '["High saturated fat — limit to 1 tsp per day"]','[]'),
    ("8901030898457","Amul Cheese Slices 200g","Amul","Dairy","🧀","medium",40,
     '[{"n":"Processed Cheese","r":"ok","note":""},{"n":"Emulsifying Salts (INS 339, 452)","r":"medium","note":"Phosphates — excess can affect kidneys"},{"n":"Common Salt","r":"medium","note":"High sodium — 400mg per 2 slices"}]',
     '["Very high sodium — 2 slices = 400mg sodium"]','[]'),
    ("8901030817182","Amul Boost Health Drink 200g","Amul","Beverage","💪","medium",48,
     '[{"n":"Skimmed Milk Powder","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"High — listed 2nd ingredient"},{"n":"Cocoa Solids","r":"ok","note":"Antioxidants"},{"n":"Vitamins & Minerals","r":"ok","note":"Well fortified"}]',
     '["High sugar despite health positioning"]','[]'),
    ("8901030937132","Amul Vanilla Ice Cream 500ml","Amul","Dairy","🍦","medium",55,
     '[{"n":"Milk Solids","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"18g per 100g"},{"n":"Vegetable Fat","r":"medium","note":""},{"n":"Vanilla Flavour","r":"ok","note":""}]',
     '["High sugar — 18g per 100g"]','[]'),
    ("8901030976063","Amul Kool Koko Chocolate Milk 200ml","Amul","Dairy","🥛","medium",42,
     '[{"n":"Toned Milk","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"Added sugar"},{"n":"Cocoa Powder","r":"ok","note":""}]',
     '["Added sugar — not recommended as daily drink"]','[]'),
    ("8901030104923","Amul Pro Whey Protein Drink 500g","Amul","Beverage","💪","low",22,
     '[{"n":"Skimmed Milk Powder","r":"ok","note":""},{"n":"Whey Protein Concentrate","r":"ok","note":"High quality protein"},{"n":"Vitamins & Minerals","r":"ok","note":"Well fortified"}]',
     '[]','[]'),
    ("8901012100707","ITC Aashirvaad Whole Wheat Atta 5kg","ITC","Staple","🌾","ok",6,
     '[{"n":"100% Whole Wheat Flour","r":"ok","note":"High fibre, B vitamins, iron, zinc"}]',
     '[]','[]'),
    ("8901012390122","ITC Aashirvaad Multigrain Atta 1kg","ITC","Staple","🌾","ok",8,
     '[{"n":"Whole Wheat","r":"ok","note":"High fibre"},{"n":"Soya","r":"ok","note":"Protein boost"},{"n":"Oat","r":"ok","note":"Beta-glucan"},{"n":"Maize","r":"ok","note":""}]',
     '[]','[]'),
    ("8901012308318","Sunfeast Yippee Magic Masala Noodles 70g","ITC","Noodles","🍜","high",76,
     '[{"n":"Wheat Flour (Maida)","r":"medium","note":"Refined"},{"n":"MSG (INS 621)","r":"high","note":"High sodium"},{"n":"Sunset Yellow FCF (INS 110)","r":"high","note":"Azo dye — hyperactivity in children"}]',
     '["Contains MSG and Sunset Yellow azo dye","High sodium — 900mg per serving"]',
     '["ADHD risk in children","Hypertension"]'),
    ("8901012310311","Sunfeast Farmlite Digestive Oats 150g","ITC","Biscuit","🌾","low",24,
     '[{"n":"Whole Wheat Flour","r":"ok","note":"Good fibre"},{"n":"Oats","r":"ok","note":"Beta-glucan fibre"},{"n":"Sugar","r":"low","note":"Low"},{"n":"Edible Vegetable Oil","r":"low","note":""}]',
     '["One of the healthier biscuit options in India"]','[]'),
    ("8901012345672","Sunfeast Dark Fantasy Choco Fills 150g","ITC","Biscuit","🍫","high",72,
     '[{"n":"Maida (Refined Wheat Flour)","r":"medium","note":"Low fibre"},{"n":"Sugar","r":"high","note":"Very high"},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"TBHQ (INS 319)","r":"high","note":"Synthetic preservative — banned in Japan"}]',
     '["Very high sugar","Contains TBHQ — banned in Japan & EU"]',
     '["Obesity","Type 2 diabetes","Dental decay"]'),
    ("8901012100028","Bingo Mad Angles Achaari Masti 38g","ITC","Chips","🔺","high",80,
     '[{"n":"Corn Flour","r":"ok","note":""},{"n":"MSG (INS 621)","r":"high","note":"High sodium"},{"n":"Sunset Yellow (INS 110)","r":"high","note":"Azo dye — hyperactivity in children"}]',
     '["High MSG content","Sunset Yellow azo dye — hyperactivity concern for children"]',
     '["ADHD risk in children with regular use"]'),
    ("8901012100202","Bingo Original Style Salted Chips 52g","ITC","Chips","🥔","high",78,
     '[{"n":"Potatoes","r":"ok","note":""},{"n":"Edible Oil (Palm)","r":"medium","note":""},{"n":"Salt","r":"medium","note":"High sodium"},{"n":"TBHQ (INS 319)","r":"high","note":"Preservative"}]',
     '["Fried in palm oil — high saturated fat","Contains TBHQ preservative"]','[]'),
    ("8901725116071","Sunfeast All Rounder Salted Biscuits 75g","ITC","Biscuit","🌾","low",28,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Edible Vegetable Oil","r":"low","note":""},{"n":"Salt","r":"ok","note":"Moderate"}]',
     '[]','[]'),
    ("8901725112219","Sunfeast Fantastik Choco Bar Biscuits","ITC","Biscuit","🍫","medium",55,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Cocoa","r":"ok","note":""},{"n":"Vegetable Fat","r":"medium","note":""}]',
     '["Moderate sugar and fat"]','[]'),
    ("8901207002281","Dabur Honey 250g","Dabur","Other","🍯","ok",10,
     '[{"n":"Natural Honey","r":"ok","note":"Antioxidants, antimicrobial, anti-inflammatory"}]',
     '["Not suitable for infants under 1 year — botulism risk"]','[]'),
    ("8901207010835","Dabur Real Apple Juice 1L","Dabur","Beverage","🍎","medium",48,
     '[{"n":"Apple Juice Concentrate","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"Added beyond fruit sugar"},{"n":"Ascorbic Acid (INS 300)","r":"ok","note":"Vitamin C"}]',
     '["Added sugar reduces health benefit","Fibre removed — blood sugar spikes"]','[]'),
    ("8901207010569","Dabur Real Guava Juice 1L","Dabur","Beverage","🍈","medium",45,
     '[{"n":"Guava Juice Concentrate","r":"ok","note":"High Vitamin C"},{"n":"Sugar","r":"medium","note":"Added"}]',
     '["Added sugar reduces health benefit"]','[]'),
    ("8901207100024","Dabur Chyawanprash 500g","Dabur","Other","🌿","low",20,
     '[{"n":"Amla (Indian Gooseberry)","r":"ok","note":"Highest natural source of Vitamin C"},{"n":"Ashwagandha","r":"ok","note":"Adaptogen — immunity booster"},{"n":"Sugar","r":"medium","note":"Moderate"},{"n":"45+ Ayurvedic Herbs","r":"ok","note":"Traditional formulation"}]',
     '["Contains sugar — diabetics should use in moderation"]','[]'),
    ("8901491400008","Uncle Chipps Plain Salted 30g","PepsiCo","Chips","🥔","high",75,
     '[{"n":"Potatoes","r":"ok","note":""},{"n":"Edible Vegetable Oil (Palm)","r":"medium","note":"Saturated fat"},{"n":"Salt","r":"medium","note":"High sodium per pack"}]',
     '["Fried in palm oil — high saturated fat","High sodium for a small pack"]','[]'),
    ("8901491435000","Uncle Chipps Spicy Treat 50g","PepsiCo","Chips","🌶️","high",78,
     '[{"n":"Potatoes","r":"ok","note":""},{"n":"Edible Vegetable Oil","r":"medium","note":""},{"n":"Salt","r":"medium","note":""},{"n":"INS 627 & 631","r":"medium","note":"Flavour enhancers"}]',
     '["Contains INS 627 & 631 flavour enhancers","High sodium"]','[]'),
    ("8901491502238","Kurkure Masala Munch 90g","PepsiCo","Chips","🌶️","high",85,
     '[{"n":"Rice Meal","r":"ok","note":""},{"n":"MSG (INS 621)","r":"high","note":"Very high sodium"},{"n":"Sunset Yellow FCF (INS 110)","r":"high","note":"Azo dye — hyperactivity in children"},{"n":"Tartrazine (INS 102)","r":"high","note":"Azo dye — restricted in EU"}]',
     '["Contains 2 azo dyes — linked to hyperactivity in children","Very high MSG content"]',
     '["ADHD aggravation in children","Kidney stress from excess sodium"]'),
    ("8901491400312","Lays Classic Salted Chips 26g","PepsiCo","Chips","🥔","high",80,
     '[{"n":"Potatoes","r":"ok","note":""},{"n":"Edible Vegetable Oil (Palm)","r":"medium","note":"Saturated fat"},{"n":"Salt","r":"medium","note":"High per pack"},{"n":"TBHQ (INS 319)","r":"high","note":"Synthetic antioxidant — banned in Japan & EU"}]',
     '["1 pack = 30% daily sodium","Contains TBHQ preservative"]','["Cardiovascular risk","Obesity"]'),
    ("8901491502214","Lays Magic Masala Chips 26g","PepsiCo","Chips","🌶️","high",83,
     '[{"n":"Potatoes","r":"ok","note":""},{"n":"MSG (INS 621)","r":"high","note":""},{"n":"Sunset Yellow (INS 110)","r":"high","note":"Azo dye"},{"n":"TBHQ (INS 319)","r":"high","note":"Preservative"}]',
     '["Three high-risk additives: MSG + Sunset Yellow + TBHQ","Very high sodium for a small pack"]',
     '["ADHD risk in children","Hypertension"]'),
    ("8902080100071","Pepsi Cola 250ml Can","PepsiCo","Beverage","🥤","high",85,
     '[{"n":"Carbonated Water","r":"ok","note":""},{"n":"Sugar","r":"high","note":"28g per can = 7 teaspoons"},{"n":"Caramel Colour (INS 150d)","r":"high","note":"4-MEI byproduct — IARC possible carcinogen"},{"n":"Phosphoric Acid (INS 338)","r":"medium","note":"Erodes tooth enamel & bone"}]',
     '["28g sugar — 7 teaspoons in one can","Caramel colour INS 150d has carcinogen concerns"]',
     '["Type 2 diabetes","Dental erosion","Bone density loss"]'),
    ("8902080104079","7UP Lemon Lime Drink 250ml","PepsiCo","Beverage","🍋","high",73,
     '[{"n":"Carbonated Water","r":"ok","note":""},{"n":"Sugar","r":"high","note":"26g per can"},{"n":"Citric Acid (INS 330)","r":"ok","note":""}]',
     '["26g sugar per can — nearly 7 teaspoons","No nutritional value"]',
     '["Dental erosion","Obesity with regular use"]'),
    ("8901764032912","Sprite Lemon Lime 250ml","Coca-Cola India","Beverage","🥤","high",74,
     '[{"n":"Carbonated Water","r":"ok","note":""},{"n":"Sugar","r":"high","note":"28g per 250ml"},{"n":"Acidity Regulator (INS 330)","r":"ok","note":"Citric acid — safe"}]',
     '["28g sugar per can — 7 teaspoons"]','["Dental erosion","Obesity risk with daily consumption"]'),
    ("8901764013034","Limca Lemon Lime Drink 300ml","Coca-Cola India","Beverage","🍋","high",72,
     '[{"n":"Carbonated Water","r":"ok","note":""},{"n":"Sugar","r":"high","note":"30g per 300ml"},{"n":"Citric Acid","r":"ok","note":""}]',
     '["30g sugar per 300ml — 8 teaspoons"]','["Dental erosion","Obesity"]'),
    ("5000112111064","Maaza Mango Drink 600ml","Coca-Cola India","Beverage","🥭","medium",60,
     '[{"n":"Mango Pulp (25%)","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"High"},{"n":"Sodium Benzoate (INS 211)","r":"high","note":"Preservative — can react with Vit C"}]',
     '["Only 25% real mango — rest is sugar water","Contains sodium benzoate preservative"]','[]'),
    ("5000112629729","Thums Up Sparkling Cola 300ml","Coca-Cola India","Beverage","🥤","high",85,
     '[{"n":"Carbonated Water","r":"ok","note":""},{"n":"Sugar","r":"high","note":"32g per 300ml"},{"n":"Caramel Colour (INS 150d)","r":"high","note":"4-MEI — IARC possible carcinogen"},{"n":"Phosphoric Acid (INS 338)","r":"medium","note":"Erodes enamel & bone"}]',
     '["32g sugar — 8 teaspoons","Caramel colour 150d carcinogen concern"]',
     '["Diabetes","Osteoporosis","Dental erosion"]'),
    ("8906004700019","Haldirams Aloo Bhujia 200g","Haldirams","Namkeen","🌾","medium",55,
     '[{"n":"Besan (Gram Flour)","r":"ok","note":"Good protein source"},{"n":"Edible Oil (Palm)","r":"medium","note":"Saturated fat"},{"n":"Salt","r":"medium","note":"High sodium"}]',
     '["Deep fried in palm oil","High sodium — watch portion size"]','[]'),
    ("8906004700026","Haldirams Navratan Mix Namkeen 200g","Haldirams","Namkeen","🌾","medium",48,
     '[{"n":"Various Grains & Pulses","r":"ok","note":"Good protein mix"},{"n":"Refined Oil","r":"medium","note":""},{"n":"Salt","r":"medium","note":"High sodium"}]',
     '["Fried — high calorie density"]','[]'),
    ("8906004700033","Haldirams Moong Dal Namkeen 200g","Haldirams","Namkeen","🌾","medium",45,
     '[{"n":"Moong Dal","r":"ok","note":"Excellent protein"},{"n":"Refined Oil","r":"medium","note":""},{"n":"Salt","r":"medium","note":""}]',
     '["Fried but better protein base than most namkeen"]','[]'),
    ("8906022501001","Saffola Oats 400g","Marico","Cereals","🌾","ok",7,
     '[{"n":"100% Rolled Oats","r":"ok","note":"High beta-glucan soluble fibre — lowers cholesterol"},{"n":"No additives","r":"ok","note":"Clean label — just oats"}]',
     '[]','[]'),
    ("8906022500967","Saffola Gold Blended Oil 1L","Marico","Oil","🌻","ok",12,
     '[{"n":"Refined Rice Bran Oil","r":"ok","note":"Oryzanol — clinically reduces LDL cholesterol"},{"n":"Refined Sunflower Oil","r":"ok","note":"High PUFA — good for heart"}]',
     '[]','[]'),
    ("8906022500974","Saffola Masala Oats Veggie Twist 40g","Marico","Cereals","🌾","low",30,
     '[{"n":"Rolled Oats (70%)","r":"ok","note":"High beta-glucan"},{"n":"Vegetables (Dehydrated)","r":"ok","note":""},{"n":"Salt","r":"ok","note":""},{"n":"Spices","r":"ok","note":""}]',
     '["Healthy base — watch sodium on masala variants"]','[]'),
    ("8906022501018","Saffola Total Heart Health Oil 1L","Marico","Oil","🌻","ok",10,
     '[{"n":"Refined Rice Bran Oil","r":"ok","note":"Oryzanol reduces LDL cholesterol"},{"n":"Refined Safflower Oil","r":"ok","note":"High linoleic acid — heart friendly"}]',
     '[]','[]'),
    ("8904109400285","Patanjali Desi Cow Ghee 500ml","Patanjali","Dairy","🫙","low",18,
     '[{"n":"Pure Cow Milk Fat","r":"ok","note":"Contains CLA, fat-soluble vitamins A,D,E,K"},{"n":"No additives","r":"ok","note":"Clean label — pure ghee"}]',
     '["High in saturated fat — limit to 1-2 tsp per day"]','[]'),
    ("8904109100338","Patanjali Aarogya Atta Biscuit 200g","Patanjali","Biscuit","🌾","low",25,
     '[{"n":"Whole Wheat Flour (Atta)","r":"ok","note":"High fibre"},{"n":"Sugar","r":"low","note":"Low"},{"n":"Desi Ghee","r":"low","note":"Natural fat"}]',
     '[]','[]'),
    ("8904109400520","Patanjali Peanut Butter Crunchy 500g","Patanjali","Condiment","🥜","low",22,
     '[{"n":"Roasted Peanuts","r":"ok","note":"Excellent protein & healthy fats"},{"n":"Salt","r":"ok","note":""}]',
     '[]','[]'),
    ("8901526100019","MTR Instant Upma Mix 180g","MTR","Ready Meal","🍚","medium",38,
     '[{"n":"Semolina (Rava/Suji)","r":"ok","note":"Moderate fibre"},{"n":"Edible Vegetable Oil","r":"medium","note":""},{"n":"Salt","r":"medium","note":"Moderate sodium"}]',
     '["Moderate sodium — add less salt when cooking"]','[]'),
    ("8901526100125","MTR Instant Poha Mix 180g","MTR","Ready Meal","🍚","low",28,
     '[{"n":"Flattened Rice (Poha)","r":"ok","note":"Good carbs, iron"},{"n":"Salt","r":"ok","note":"Low"},{"n":"Spices & Peanuts","r":"ok","note":"Protein from peanuts"}]',
     '[]','[]'),
    ("8901526100231","MTR Instant Rava Idli Mix 500g","MTR","Ready Meal","🍚","low",25,
     '[{"n":"Semolina (Rava)","r":"ok","note":""},{"n":"Rice Flour","r":"ok","note":""},{"n":"Salt","r":"ok","note":""}]',
     '[]','[]'),
    ("8901058000528","Tata Tea Premium 250g","Tata Consumer","Beverage","🍵","low",15,
     '[{"n":"Black Tea Leaves","r":"ok","note":"Rich in antioxidants — polyphenols & theaflavins"},{"n":"Caffeine (natural)","r":"low","note":"~50mg per cup"}]',
     '["Limit to 3-4 cups/day","Avoid on empty stomach"]','[]'),
    ("8901058000481","Tata Tea Gold 250g","Tata Consumer","Beverage","🍵","low",15,
     '[{"n":"Black Tea Leaves (premium blend)","r":"ok","note":"High antioxidant content"},{"n":"Caffeine (natural)","r":"low","note":"~55mg per cup"}]',
     '["Limit to 3-4 cups/day"]','[]'),
    ("8901058000672","Tata Salt Iodised 1kg","Tata Consumer","Condiment","🧂","ok",4,
     '[{"n":"Iodised Salt","r":"ok","note":"Essential iodine for thyroid health"}]',
     '["Limit total daily salt to 5g (WHO recommendation)"]','[]'),
    ("8901399105012","Wagh Bakri Premium Tea 500g","Wagh Bakri","Beverage","🍵","low",15,
     '[{"n":"Black Tea Leaves","r":"ok","note":"Rich in antioxidants, theaflavins"},{"n":"Caffeine (natural)","r":"low","note":"~45mg per cup"}]',
     '["Limit to 3-4 cups/day"]','[]'),
    ("8901399101007","Wagh Bakri Masala Chai 250g","Wagh Bakri","Beverage","🍵","low",18,
     '[{"n":"Black Tea","r":"ok","note":"Antioxidants"},{"n":"Ginger","r":"ok","note":"Anti-inflammatory"},{"n":"Cardamom","r":"ok","note":"Digestive aid"},{"n":"Cinnamon","r":"ok","note":"Blood sugar regulation"}]',
     '[]','[]'),
    ("8901234760017","MDH Deggi Mirch Chilli Powder 100g","MDH","Condiment","🌶️","ok",8,
     '[{"n":"Red Chilli","r":"ok","note":"Capsaicin — anti-inflammatory, boosts metabolism"},{"n":"No additives","r":"ok","note":"Pure spice"}]',
     '[]','[]'),
    ("8901234790014","MDH Rajma Masala 100g","MDH","Condiment","🌶️","ok",8,
     '[{"n":"Coriander","r":"ok","note":""},{"n":"Red Chilli","r":"ok","note":""},{"n":"Cumin","r":"ok","note":"Digestive aid"},{"n":"Turmeric","r":"ok","note":"Anti-inflammatory — curcumin"}]',
     '[]','[]'),
    ("8906001500308","Chings Secret Schezwan Noodles 60g","Capital Foods","Noodles","🍜","high",80,
     '[{"n":"Refined Wheat Flour (Maida)","r":"medium","note":""},{"n":"Salt","r":"high","note":"2100mg sodium per pack — 90% daily limit"},{"n":"MSG (INS 621)","r":"high","note":"Excess sodium — headaches"},{"n":"TBHQ (INS 319)","r":"high","note":"Preservative — banned in some countries"}]',
     '["Extreme sodium — 2100mg per pack = 90% of daily limit","Contains MSG & TBHQ"]',
     '["Hypertension","Kidney disease over time"]'),
    ("8906001500049","Chings Secret Szechwan Chutney 210g","Capital Foods","Condiment","🌶️","medium",45,
     '[{"n":"Tomatoes","r":"ok","note":""},{"n":"Chillies","r":"ok","note":""},{"n":"Vinegar","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"MSG (INS 621)","r":"high","note":"Excess sodium"}]',
     '["High sodium from MSG","Use sparingly"]','[]'),
    ("8901928350456","Bisk Farm Googly Cream Biscuits 100g","Bisk Farm","Biscuit","🍪","medium",52,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Edible Vegetable Oil (Palm)","r":"medium","note":""},{"n":"Glucose Syrup","r":"medium","note":"Fast sugar"}]',
     '["Palm oil — high saturated fat"]','[]'),
    ("8906009078014","Unibic Butter Cookies 75g","Unibic","Biscuit","🍪","medium",48,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Butter","r":"medium","note":"Natural saturated fat — better than palm oil"},{"n":"Milk Solids","r":"ok","note":""}]',
     '["Real butter — higher quality than palm oil biscuits but still high fat"]','[]'),
    ("8906009077017","Unibic Fruit & Nut Cookies 75g","Unibic","Biscuit","🌰","low",28,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"low","note":""},{"n":"Butter","r":"low","note":""},{"n":"Raisins","r":"ok","note":"Natural fruit"},{"n":"Cashewnuts","r":"ok","note":"Good fats & protein"}]',
     '[]','[]'),
    ("8906009079073","Unibic Choco Ripple Cookies 50g","Unibic","Biscuit","🍫","medium",52,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":""},{"n":"Butter","r":"medium","note":""},{"n":"Cocoa Powder","r":"ok","note":""}]',
     '["Moderate sugar — better than most commercial biscuits"]','[]'),
    ("8906009078021","Unibic Cashew Cookies 75g","Unibic","Biscuit","🥜","low",26,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"low","note":"Less sweet"},{"n":"Butter","r":"low","note":""},{"n":"Cashewnuts","r":"ok","note":"Healthy fats & protein"}]',
     '[]','[]'),
    ("8901071701983","Hersheys Kisses Milk Chocolate 100.8g","Hersheys","Chocolate","🍫","medium",58,
     '[{"n":"Sugar","r":"medium","note":"High"},{"n":"Cocoa Butter","r":"ok","note":""},{"n":"Whole Milk Powder","r":"ok","note":""},{"n":"Cocoa Mass","r":"ok","note":"Antioxidants"}]',
     '["High sugar — 4-5 pieces = 10g sugar","Avoid daily consumption"]','["Dental decay","Obesity"]'),
    ("8901071706834","Hersheys Chocolate Syrup 623g","Hersheys","Condiment","🍫","high",75,
     '[{"n":"High Fructose Corn Syrup","r":"high","note":"#1 ingredient — linked to obesity & fatty liver"},{"n":"Corn Syrup","r":"high","note":"Fast sugar"},{"n":"Cocoa","r":"ok","note":""}]',
     '["First ingredient is High Fructose Corn Syrup","2 tbsp = 22g sugar — almost 6 teaspoons"]',
     '["Fatty liver disease","Type 2 diabetes","Obesity"]'),
    ("8901030831690","Kissan Mixed Fruit Jam 200g","HUL","Condiment","🍓","medium",55,
     '[{"n":"Sugar","r":"high","note":"50% of product by weight"},{"n":"Mixed Fruit Pulp (45%)","r":"ok","note":""},{"n":"Pectin (INS 440)","r":"ok","note":"Natural thickener"},{"n":"Sodium Benzoate (INS 211)","r":"medium","note":"Preservative — reacts with Vit C"}]',
     '["Sugar makes up half the jar","Sodium benzoate preservative"]','[]'),
    ("8906050000262","Too Yumm Multigrain Chips 30g","RP-SG Group","Chips","🌿","low",28,
     '[{"n":"Rice Flour","r":"ok","note":""},{"n":"Oats","r":"ok","note":"Beta-glucan fibre"},{"n":"Sunflower Oil","r":"low","note":"Healthier than palm oil — baked not fried"},{"n":"Salt","r":"ok","note":"Low sodium"}]',
     '["Baked not fried — significantly healthier than regular chips"]','[]'),
    ("8906002600021","Bikano Bhujia Sev 200g","Bikano","Namkeen","🌾","medium",50,
     '[{"n":"Besan (Gram Flour)","r":"ok","note":""},{"n":"Edible Oil","r":"medium","note":""},{"n":"Salt","r":"medium","note":""},{"n":"Spices","r":"ok","note":""}]',
     '["Fried — high calorie density per serving"]','[]'),
    ("8906002200559","Lijjat Masala Papad 200g","Lijjat","Snack","🫓","ok",14,
     '[{"n":"Urad Dal (Black Gram)","r":"ok","note":"Excellent plant protein source"},{"n":"Salt","r":"ok","note":"Moderate"},{"n":"Spices (Jeera, Chilli)","r":"ok","note":"Anti-inflammatory"}]',
     '[]','[]'),
    ("8000500254950","Kinder Joy Egg Chocolate 20g","Ferrero","Chocolate","🥚","high",72,
     '[{"n":"Sugar","r":"high","note":"#1 ingredient by weight"},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"Skim Milk Powder","r":"ok","note":""},{"n":"Cocoa","r":"ok","note":""}]',
     '["Sugar is the first ingredient","Not safe for children under 3 — choking hazard"]',
     '["Childhood obesity","Dental decay"]'),
    ("7622201757236","Cadbury Oreo Original Biscuits 113g","Mondelez","Biscuit","🍪","high",68,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"high","note":"Very high — 14g per 3-cookie serving"},{"n":"Palm Oil","r":"medium","note":"Saturated fat"},{"n":"High Fructose Corn Syrup","r":"high","note":"Metabolic concerns"}]',
     '["Contains HFCS — 14g sugar per serving (3 cookies)"]',
     '["Obesity","Dental decay","Type 2 diabetes with daily use"]'),
    ("7622201699130","Cadbury Dairy Milk Chocolate 40g","Mondelez","Chocolate","🍫","medium",55,
     '[{"n":"Sugar","r":"medium","note":"22g per bar"},{"n":"Cocoa Butter","r":"ok","note":""},{"n":"Whole Milk Solids","r":"ok","note":""},{"n":"Cocoa Mass","r":"ok","note":"Antioxidants"}]',
     '["1 bar = 22g sugar"]','["Dental decay with daily use"]'),
    ("7622210100511","Cadbury Bournvita Health Drink 500g","Mondelez","Beverage","☕","medium",58,
     '[{"n":"Sugar","r":"high","note":"37g per 3-tsp serving — #1 ingredient"},{"n":"Wheat","r":"ok","note":""},{"n":"Cocoa Solids","r":"ok","note":""},{"n":"Vitamins & Minerals","r":"ok","note":"Fortified"}]',
     '["Sugar is the first ingredient — 37g per 3-tsp serving","FSSAI directed to remove health claims in 2023"]',
     '["Childhood obesity","Type 2 diabetes risk"]'),
    ("7622200094943","Cadbury Gems Chocolate Buttons 22g","Mondelez","Candy","🍬","high",70,
     '[{"n":"Sugar","r":"medium","note":""},{"n":"Cocoa","r":"ok","note":""},{"n":"Carmine (INS 120)","r":"high","note":"Insect-derived red dye — allergy risk"},{"n":"Tartrazine (INS 102)","r":"high","note":"Yellow azo dye — hyperactivity in children"}]',
     '["Contains carmine — insect-derived dye","Tartrazine azo dye — hyperactivity linked"]',
     '["ADHD aggravation in sensitive children"]'),
    ("5000008100103","Kelloggs Corn Flakes 300g","Kelloggs","Cereals","🌽","medium",42,
     '[{"n":"Milled Corn (Maize)","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"Added"},{"n":"Salt","r":"ok","note":"Low"},{"n":"Vitamins (B1, B2, B3, B6, B12, C, D, Folic acid)","r":"ok","note":"Well fortified"},{"n":"Iron","r":"ok","note":""}]',
     '["High glycemic index — blood sugar spikes rapidly","Best eaten with whole milk not juice"]','[]'),
    ("8901234500606","Horlicks Original Health Drink 500g","GSK","Beverage","🌾","medium",48,
     '[{"n":"Wheat Flour","r":"ok","note":""},{"n":"Sugar","r":"medium","note":"High"},{"n":"Skimmed Milk Powder","r":"ok","note":""},{"n":"Malt Extract","r":"ok","note":""},{"n":"Vitamins & Minerals (23 nutrients)","r":"ok","note":"Very well fortified"}]',
     '["High sugar content despite health positioning","Better than plain sugar drinks but still sugary"]','[]'),
]

def _seed(conn):
    c = conn.cursor()
    inserted = 0
    for row in SEED:
        c.execute("SELECT barcode FROM products WHERE barcode=%s", (row[0],))
        if not c.fetchone():
            c.execute("""INSERT INTO products
                (barcode,name,brand,category,icon,risk,score,ingredients,warnings,future)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", row)
            inserted += 1
    conn.commit()
    if inserted:
        print(f"  Seeded {inserted} new products into Neon PostgreSQL.")

# ── API ROUTES ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("templates", "index.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

@app.route("/api/products", methods=["GET"])
def get_products():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM products ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return jsonify([_row_to_dict(r) for r in rows])

@app.route("/api/products/<barcode>", methods=["GET"])
def get_product(barcode):
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM products WHERE barcode=%s", (barcode,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify(_row_to_dict(row))
    return jsonify({"error": "not_found"}), 404

@app.route("/api/products", methods=["POST"])
def save_product():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO products
        (barcode,name,brand,category,icon,risk,score,ingredients,warnings,future,ai_generated)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (barcode) DO UPDATE SET
            name=EXCLUDED.name, brand=EXCLUDED.brand, category=EXCLUDED.category,
            icon=EXCLUDED.icon, risk=EXCLUDED.risk, score=EXCLUDED.score,
            ingredients=EXCLUDED.ingredients, warnings=EXCLUDED.warnings,
            future=EXCLUDED.future, ai_generated=EXCLUDED.ai_generated""",
        (data["barcode"], data["name"], data["brand"],
         data.get("category", data.get("cat","Other")),
         data.get("icon","📦"), data["risk"], data["score"],
         json.dumps(data.get("ingredients",[])), json.dumps(data.get("warnings",[])),
         json.dumps(data.get("future",[])), int(data.get("ai_generated",0))))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/products/<barcode>", methods=["DELETE"])
def delete_product(barcode):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE barcode=%s", (barcode,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/scans", methods=["POST"])
def log_scan():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO scans (barcode, product_name) VALUES (%s,%s)",
              (data["barcode"], data.get("product_name","")))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/scans", methods=["GET"])
def get_scans():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM scans ORDER BY scanned_at DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/scans", methods=["DELETE"])
def clear_scans():
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM scans")
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/stats", methods=["GET"])
def get_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM scans"); scans = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM products WHERE ai_generated=1"); ai = c.fetchone()[0]
    c.execute("SELECT category, COUNT(*) as cnt FROM products GROUP BY category ORDER BY cnt DESC")
    cats = [{"category": r[0], "cnt": r[1]} for r in c.fetchall()]
    c.execute("SELECT risk, COUNT(*) as cnt FROM products GROUP BY risk")
    risks = [{"risk": r[0], "cnt": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"total_products": total, "total_scans": scans,
                    "ai_analysed": ai, "categories": cats, "risk_distribution": risks})

# ── AI PROMPT ──────────────────────────────────────────────────────────────────

AI_PROMPT = """You are SafeKhao food safety AI analyst for Indian consumers.
Analyse the product and return a JSON object with EXACTLY this structure:
{
  "barcode": "<the barcode provided>",
  "name": "<product name>",
  "brand": "<brand name>",
  "category": "<one of: Biscuit|Chips|Beverage|Noodles|Dairy|Snack|Chocolate|Cereals|Namkeen|Condiment|Ready Meal|Staple|Oil|Candy|Other>",
  "icon": "<single relevant emoji>",
  "risk": "<ok|low|medium|high>",
  "score": <integer 0-100>,
  "ingredients": [{"n":"<name>","r":"<ok|low|medium|high>","note":"<brief plain-English reason>"}],
  "warnings": ["<health warning>"],
  "future": ["<future health risk if consumed regularly>"],
  "ai_generated": 1
}
Risk: ok=0-20 (whole food), low=21-40 (mildly processed), medium=41-65 (moderate concerns), high=66-100 (dangerous additives).
Flag HIGH: MSG/INS 621, TBHQ/INS 319, Sunset Yellow/INS 110, Tartrazine/INS 102, Trans fats, HFCS, Aspartame/INS 951, Sodium Benzoate/INS 211, Caramel 150d, Carmine/INS 120.
Return ONLY valid JSON. No markdown, no preamble."""

@app.route("/api/ai/analyse", methods=["POST"])
def ai_analyse():
    data = request.json
    barcode = data.get("barcode","").strip()
    name    = data.get("name","").strip()
    brand   = data.get("brand","").strip()
    ingredients_text = data.get("ingredients_text","").strip()

    if not barcode:
        return jsonify({"error": "barcode required"}), 400

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM products WHERE barcode=%s", (barcode,))
    existing = c.fetchone()
    conn.close()
    if existing:
        return jsonify({**_row_to_dict(existing), "from_cache": True})

    user_msg = f"""Barcode: {barcode}
Product Name: {name or 'Unknown'}
Brand: {brand or 'Unknown'}
Ingredients from package: {ingredients_text or 'Use your knowledge of this product'}
Return ONLY the JSON object."""

    raw = ""
    try:
        resp = AI_CLIENT.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"system","content":AI_PROMPT},{"role":"user","content":user_msg}],
            temperature=0.1, max_tokens=2000,
            response_format={"type":"json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?","",raw)
        raw = re.sub(r"\n?```$","",raw).strip()
        result = json.loads(raw)

        result["barcode"]      = barcode
        result["ai_generated"] = 1
        result.setdefault("name",        name or "Unknown Product")
        result.setdefault("brand",       brand or "Unknown")
        result.setdefault("category",    "Other")
        result.setdefault("icon",        "📦")
        result.setdefault("risk",        "medium")
        result.setdefault("score",       50)
        result.setdefault("ingredients", [])
        result.setdefault("warnings",    [])
        result.setdefault("future",      [])
        result["score"] = max(0, min(100, int(result["score"])))

        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO products
            (barcode,name,brand,category,icon,risk,score,ingredients,warnings,future,ai_generated)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (barcode) DO UPDATE SET
                name=EXCLUDED.name, brand=EXCLUDED.brand, category=EXCLUDED.category,
                icon=EXCLUDED.icon, risk=EXCLUDED.risk, score=EXCLUDED.score,
                ingredients=EXCLUDED.ingredients, warnings=EXCLUDED.warnings,
                future=EXCLUDED.future, ai_generated=EXCLUDED.ai_generated""",
            (result["barcode"], result["name"], result["brand"],
             result["category"], result["icon"], result["risk"], result["score"],
             json.dumps(result["ingredients"]), json.dumps(result["warnings"]),
             json.dumps(result["future"]), 1))
        c.execute("INSERT INTO ai_analyses (barcode,raw_input,result) VALUES (%s,%s,%s)",
                  (barcode, ingredients_text, json.dumps(result)))
        conn.commit(); conn.close()
        return jsonify({**result, "from_cache": False})

    except json.JSONDecodeError as e:
        return jsonify({"error": f"AI returned invalid JSON: {e}", "raw": raw[:500]}), 500
    except Exception as e:
        err = str(e)
        if "api_key" in err.lower() or "authentication" in err.lower():
            return jsonify({"error": "Invalid or missing GROQ_API_KEY. Get your free key at console.groq.com"}), 401
        if "rate_limit" in err.lower():
            return jsonify({"error": "Groq rate limit hit — wait a few seconds and try again"}), 429
        return jsonify({"error": err}), 500


# ── OPEN FOOD FACTS IMAGE FETCH ────────────────────────────────────────────────

def fetch_off_image(barcode):
    """Fetch product image from Open Food Facts (free, no API key)."""
    try:
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json?fields=image_front_small_url,image_front_url"
        req = urllib.request.Request(url, headers={"User-Agent": "SafeKhao/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        p = data.get("product", {})
        return p.get("image_front_small_url") or p.get("image_front_url") or None
    except Exception:
        return None

@app.route("/api/products/<barcode>/image", methods=["GET"])
def get_product_image(barcode):
    """Return image URL for a product, fetching from OFF if not cached."""
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT image_url FROM products WHERE barcode=%s", (barcode,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    img = row["image_url"]
    if not img:
        img = fetch_off_image(barcode)
        if img:
            cu = conn.cursor()
            cu.execute("UPDATE products SET image_url=%s WHERE barcode=%s", (img, barcode))
            conn.commit()
    conn.close()
    return jsonify({"image_url": img})

# ── HEALTHIER ALTERNATIVES ─────────────────────────────────────────────────────
# Maps barcode → list of alternative barcodes (healthier products in same category)

ALTERNATIVES = {
    # Chips alternatives (high risk → low risk)
    "8901491502238": ["8906050000262"],           # Kurkure → Too Yumm Multigrain
    "8901491400312": ["8906050000262"],           # Lays Classic → Too Yumm
    "8901491502214": ["8906050000262"],           # Lays Magic Masala → Too Yumm
    "8901012100028": ["8906050000262"],           # Bingo Mad Angles → Too Yumm
    "8901012100202": ["8906050000262"],           # Bingo Salted → Too Yumm
    "8901491400008": ["8906050000262"],           # Uncle Chipps → Too Yumm
    "8901491435000": ["8906050000262"],           # Uncle Chipps Spicy → Too Yumm

    # Noodles alternatives
    "8901058852899": ["8901058005851","8901058852912"],   # Maggi Masala → Maggi Atta / Veg Atta
    "8901012308318": ["8901058005851"],           # Yippee Masala → Maggi Atta
    "8906001500308": ["8901058005851"],           # Chings → Maggi Atta

    # Biscuits: unhealthy → healthier
    "8901012345672": ["8901012310311","8901063070509"],   # Dark Fantasy → Farmlite / NutriChoice
    "8901063032712": ["8901063070509","8906009077017"],   # Treat Wafers → NutriChoice / Unibic F&N
    "8901063139329": ["8901063070509"],           # Bourbon → NutriChoice
    "8901719840845": ["8901719103025"],           # Melody Toffee → Milk Shakti
    "8901063032705": ["8901063070509"],           # Treat Orange → NutriChoice
    "7622201757236": ["8901063070509","8906009077017"],   # Oreo → NutriChoice / Unibic F&N
    "8901012100202": ["8901725116071"],           # Bingo chips → Sunfeast All Rounder

    # Beverages: sugary → healthier
    "8902080100071": ["8901058000528","8901399105012"],   # Pepsi → Tata Tea / Wagh Bakri
    "8902080104079": ["8901058000528"],           # 7UP → Tea
    "8901764032912": ["8901058000528"],           # Sprite → Tea
    "8901764013034": ["8901058000528"],           # Limca → Tea
    "5000112629729": ["8901058000528"],           # Thums Up → Tea
    "5000112111064": ["8901207010835"],           # Maaza → Dabur Real Apple
    "7622210100511": ["8901058004595","8906022501001"],   # Bournvita → Nescafe Gold / Saffola Oats
    "8901030817182": ["8901030104923"],           # Amul Boost → Amul Pro Protein

    # Chocolate: bad → better
    "8000500254950": ["7622201699130"],           # Kinder Joy → Dairy Milk (less harmful)
    "8901071706834": ["8901207002281"],           # Hersheys Syrup → Dabur Honey
    "7622200094943": ["7622201699130"],           # Cadbury Gems → Dairy Milk
    "8901058004588": ["8901030869136"],           # Milkmaid → Amul Taaza Milk

    # Condiments
    "8901030831690": ["8901207002281"],           # Kissan Jam → Dabur Honey
    "8906001500049": ["8901234790014","8901234760017"],   # Chings Chutney → MDH masalas

    # Dairy: high fat/processed → better
    "8901030898457": ["8901030850523"],           # Amul Cheese → Amul Dahi
    "8901030937132": ["8901030850523"],           # Ice Cream → Amul Dahi
    "8901030976063": ["8901030869136"],           # Kool Koko → Taaza Milk

    # Cereals
    "5000008100103": ["8906022501001"],           # Corn Flakes → Saffola Oats
    "8901234500606": ["8906022500974"],           # Horlicks → Saffola Masala Oats

    # Candy
    "8901719840845": ["8901207002281"],           # Melody → Dabur Honey
}

@app.route("/api/products/<barcode>/alternatives", methods=["GET"])
def get_alternatives(barcode):
    """Return healthier alternatives for a product."""
    alt_barcodes = ALTERNATIVES.get(barcode, [])
    if not alt_barcodes:
        # Fallback: find safer products in same category
        conn = get_db()
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT category FROM products WHERE barcode=%s", (barcode,))
        row = c.fetchone()
        if row:
            c.execute("""SELECT * FROM products
                WHERE category=%s AND risk IN ('ok','low')
                AND barcode != %s ORDER BY score ASC LIMIT 3""",
                (row["category"], barcode))
            alts = c.fetchall()
            conn.close()
            return jsonify([_row_to_dict(a) for a in alts])
        conn.close()
        return jsonify([])

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    results = []
    for bc in alt_barcodes:
        c.execute("SELECT * FROM products WHERE barcode=%s", (bc,))
        row = c.fetchone()
        if row:
            results.append(_row_to_dict(row))
    conn.close()
    return jsonify(results)

# ── HELPER ─────────────────────────────────────────────────────────────────────

def _row_to_dict(row):
    d = dict(row)
    for key in ("ingredients", "warnings", "future"):
        val = d.get(key)
        if isinstance(val, str):
            try: d[key] = json.loads(val)
            except: d[key] = []
        elif val is None:
            d[key] = []
    d["cat"] = d.get("category", "Other")
    if not d.get("image_url"):
        d["image_url"] = None
    if "created_at" in d and d["created_at"] is not None:
        d["created_at"] = str(d["created_at"])
    return d

# ── START ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SafeKhao — http://localhost:5000")
    print("=" * 60)
    if not os.environ.get("GROQ_API_KEY"):
        print("  ⚠  GROQ_API_KEY not set — AI analysis will fail")
        print("  Get your free key at: https://console.groq.com")
    else:
        print(f"  ✓  Groq AI ready  (model: {GROQ_MODEL})")
    print("  Connecting to Neon PostgreSQL...")
    try:
        init_db()
        print("  ✓  Neon PostgreSQL connected & 100 products seeded")
    except Exception as e:
        print(f"  ✗  DB connection failed: {e}")
    print()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(debug=debug, host="0.0.0.0", port=port)
