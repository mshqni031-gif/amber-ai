import os
import json
import hashlib
import requests
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Load .env
load_dotenv()

from core.persona import MASTER_SYSTEM_INSTRUCTION, load_master_dossiers
from core.database import (
    init_db, 
    save_message, 
    get_all_sessions, 
    get_session_details, 
    get_admin_stats, 
    delete_session,
    delete_multiple_sessions,
    get_all_client_sessions
)

# Initialize Database on boot
init_db()

app = FastAPI(title="Amber - AI Mentor & Journal")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Load knowledge base dossiers
compiled_knowledge = load_master_dossiers(DATA_DIR)

class ChatRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = "default_session"
    history: Optional[List[dict]] = []
    image_base64: Optional[str] = None
    image_mime_type: Optional[str] = "image/jpeg"
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_content: Optional[str] = None
    gender: Optional[str] = "auto"
    user_name: Optional[str] = "User"
    user_avatar: Optional[str] = None
    api_key: Optional[str] = None

@app.get("/api/user/sessions")
async def get_client_sessions():
    """Returns stored sessions from SQLite for client chat persistence."""
    return get_all_client_sessions()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    admin_file = os.path.join(STATIC_DIR, "admin.html")
    with open(admin_file, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/status")
async def get_status():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return {
        "has_api_key": bool(api_key),
        "engine": "Gemini 3.5 Flash-Lite / Pro (Live AI Connected)"
    }

@app.post("/api/save_key")
async def save_key(req: dict):
    key = req.get("api_key", "").strip()
    if key:
        env_path = os.path.join(BASE_DIR, ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"GEMINI_API_KEY={key}\n")
        os.environ["GEMINI_API_KEY"] = key
        return {"status": "success", "message": "API key successfully saved in .env"}
    return {"status": "error", "message": "API key cannot be empty"}

# ================= OWNER AUTHENTICATION =================
def get_owner_token():
    admin_pw = os.environ.get("ADMIN_PASSWORD", "amber2026")
    return hashlib.sha256(admin_pw.encode("utf-8")).hexdigest()

def verify_owner(request: Request) -> bool:
    expected = get_owner_token()
    token = request.cookies.get("amber_owner_session")
    if token and token == expected:
        return True
    header_token = request.headers.get("X-Admin-Token")
    if header_token and header_token == expected:
        return True
    return False

@app.post("/api/admin/login")
async def admin_login(req: dict, response: Response):
    password = req.get("password", "").strip()
    expected_pw = os.environ.get("ADMIN_PASSWORD", "amber2026")
    if password == expected_pw:
        token = get_owner_token()
        response.set_cookie("amber_owner_session", token, max_age=60*60*24*30, httponly=False, samesite="lax")
        return {"status": "success", "message": "Owner authenticated successfully", "token": token}
    return JSONResponse(status_code=401, content={"status": "error", "message": "Ghalat Password! Barah-e-karam durust password darj karein."})

@app.post("/api/admin/logout")
async def admin_logout(response: Response):
    response.delete_cookie("amber_owner_session")
    return {"status": "success", "message": "Logged out successfully"}

@app.get("/api/admin/check_auth")
async def admin_check_auth(request: Request):
    return {"is_owner": verify_owner(request)}

@app.post("/api/admin/change_password")
async def admin_change_password(req: dict, request: Request, response: Response):
    if not verify_owner(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized."})
    new_pw = req.get("new_password", "").strip()
    if len(new_pw) < 4:
        return JSONResponse(status_code=400, content={"error": "Password kam az kam 4 characters ka hona chahiye."})
    os.environ["ADMIN_PASSWORD"] = new_pw
    env_path = os.path.join(BASE_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("ADMIN_PASSWORD="):
                    lines.append(line)
    lines.append(f"ADMIN_PASSWORD={new_pw}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    token = get_owner_token()
    response.set_cookie("amber_owner_session", token, max_age=60*60*24*30, httponly=False, samesite="lax")
    return {"status": "success", "message": "Password kamyabi se tabdeel ho gaya!"}

# ================= ADMIN APIS (FOR OWNER ONLY) =================
@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    if not verify_owner(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Owner login required."})
    return get_admin_stats()

@app.get("/api/admin/sessions")
async def admin_sessions(request: Request):
    if not verify_owner(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Owner login required."})
    return get_all_sessions()

@app.get("/api/admin/session/{session_id}")
async def admin_session_detail(session_id: str, request: Request):
    if not verify_owner(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Owner login required."})
    data = get_session_details(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return data

@app.delete("/api/admin/session/{session_id}")
async def admin_delete_session(session_id: str, request: Request):
    if not verify_owner(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Owner login required."})
    delete_session(session_id)
    return {"status": "success", "message": f"Session {session_id} deleted."}

@app.post("/api/admin/sessions/bulk-delete")
async def admin_bulk_delete_sessions(req: dict, request: Request):
    if not verify_owner(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Owner login required."})
    session_ids = req.get("session_ids", [])
    if not isinstance(session_ids, list) or not session_ids:
        return JSONResponse(status_code=400, content={"error": "No session IDs provided."})
    count = delete_multiple_sessions(session_ids)
    return {"status": "success", "message": f"{count} sessions deleted.", "count": count}

def detect_user_language(text: str) -> str:
    """Detects whether user prompt is primarily English ('en') or Roman Urdu ('ur')."""
    t = text.lower().strip()
    words = [w.strip(".,!?:;\"'()[]{}") for w in t.split()]
    if not words:
        return "ur"
    
    # Specific English greeting phrases
    if any(phrase in t for phrase in ["how are you", "how r u", "hello how", "hi how", "good morning", "good evening", "how do you do"]):
        return "en"
    # Specific Urdu greeting phrases
    if any(phrase in t for phrase in ["kaise ho", "kese ho", "kaisi ho", "kaise hain", "kaisi hain", "kya haal", "kia haal", "kaisa guzra"]):
        return "ur"

    english_vocab = {
        "hello", "hi", "hey", "how", "are", "you", "i", "am", "is", "what", "why",
        "where", "when", "who", "which", "do", "does", "did", "can", "could", "will",
        "would", "should", "the", "this", "that", "these", "those", "my", "your", "his",
        "her", "their", "our", "me", "him", "them", "us", "good", "fine", "well", "doing",
        "day", "purpose", "chatbot", "career", "problem", "friend", "advice", "help",
        "please", "thank", "thanks", "about", "tell", "explain", "think", "feel", "discuss",
        "today", "life", "matter", "something", "gorgeous"
    }

    urdu_vocab = {
        "salam", "assalam", "asalam", "walaikum", "kaise", "kaisi", "kese", "kya", "kia", "kyun",
        "kyu", "haan", "nahi", "na", "mujhe", "mera", "meri", "mere", "hum", "aap", "ap", "tum",
        "acha", "achha", "bohot", "bahut", "hai", "hain", "ho", "tha", "thi", "the", "gaya",
        "gayi", "gaye", "karta", "karti", "karte", "karo", "karein", "karna", "ke", "ki", "ka",
        "ko", "se", "par", "pe", "mein", "mai", "main", "toh", "to", "phir", "din", "baat",
        "kirdar", "novel", "masla", "faisla", "zindagi", "dil", "soch", "uljhan", "aaj"
    }

    en_count = sum(1 for w in words if w in english_vocab)
    ur_count = sum(1 for w in words if w in urdu_vocab)

    if en_count > ur_count:
        return "en"
    elif ur_count > en_count:
        return "ur"
    else:
        if words[0] in ["hello", "hi", "hey"]:
            return "en"
        if words[0] in ["salam", "assalam", "aoa"]:
            return "ur"
        return "ur"

# ================= CHAT API =================
@app.post("/api/chat")
async def handle_chat(req: ChatRequest, request: Request):
    user_msg = req.message.strip()
    session_id = req.session_id or "default_session"
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_name = (req.user_name or "User").strip()
    
    # Save user message to persistent DB for Owner monitoring & history
    log_content = user_msg
    if req.image_base64:
        log_content = f"[🖼️ Image Attached] {user_msg}".strip()
    save_message(session_id=session_id, role="user", content=log_content, user_ip=client_ip, user_name=user_name, user_avatar=req.user_avatar)

    api_key = req.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        reply_err = "⚠️ Barah-e-karam apni Google AI Studio API key save karein."
        save_message(session_id=session_id, role="model", content=reply_err, user_ip=client_ip, user_name=user_name)
        return {
            "reply": reply_err,
            "is_live_ai": False
        }

    # Determine / Infer User Gender
    user_gender = (req.gender or "auto").lower()
    msg_lower = user_msg.lower()

    female_indicators = [
        "female", "larki", "aurat", "girl", "woman", "karti hoon", "gayi thi", 
        "soch rahi hoon", "soch rahi thi", "bata rahi hoon", "behan hoon", "meri shaadi"
    ]
    male_indicators = [
        "male", "larka", "mard", "boy", "man", "karta hoon", "gaya tha", 
        "soch raha hoon", "soch raha tha", "bata raha hoon", "bhai hoon"
    ]

    if user_gender == "auto":
        for ind in female_indicators:
            if ind in msg_lower:
                user_gender = "female"
                break
        if user_gender == "auto":
            for ind in male_indicators:
                if ind in msg_lower:
                    user_gender = "male"
                    break
        if user_gender == "auto" and req.history:
            for h in req.history:
                if h.get("role") == "user":
                    h_low = h.get("content", "").lower()
                    if any(ind in h_low for ind in female_indicators):
                        user_gender = "female"
                        break
                    elif any(ind in h_low for ind in male_indicators):
                        user_gender = "male"
                        break

    # Detect user language (English vs Roman Urdu)
    user_lang = detect_user_language(user_msg)

    # Build Gender Instruction
    gender_instruction = ""
    if user_gender == "female":
        gender_instruction = (
            "\n[STRICT GENDER MANDATE: The user is a FEMALE (Larki / Aurat).]\n"
            "- Aapse guftagu mein laazmi taur par mu'annas (feminine) seeghe aur adab baratna hai: "
            "'Kaisi hain aap?', 'Toh phir kaisa guzra aaj ka din aapka?', 'Aap kya soch rahi hain?', 'Aap theek keh rahi hain', 'Aap pareshan na hon'.\n"
            "- Kisi bhi jumlay mein muzakkar (jaise 'kaise hain', 'soch rahe hain') bilkul use nahi karna!\n"
        )
    elif user_gender == "male":
        gender_instruction = (
            "\n[STRICT GENDER MANDATE: The user is a MALE (Larka / Mard).]\n"
            "- Aapse guftagu mein muzakkar (masculine) seeghe baratne hain: "
            "'Kaise hain aap?', 'Toh phir kaisa guzra aaj ka din aapka?', 'Aap kya soch rahe hain?', 'Aap theek keh rahe hain'.\n"
        )

    # Check if user sent a greeting
    user_words = msg_lower.split()
    greeting_triggers = ["salam", "assalam", "asalam", "aoa", "slm", "wsalam", "hello", "hi", "hey"]
    has_greeting_word = any(
        any(w.startswith(gt) or gt == w for gt in greeting_triggers)
        for w in user_words
    ) or any(phrase in msg_lower for phrase in ["how are you", "kaise ho", "kese ho", "kaisi ho", "kaise hain", "kaisi hain", "kya haal", "kia haal"])

    is_pure_greeting = has_greeting_word and len(user_words) <= 7

    # Greeting vs Direct Topic Instructions based on Language
    if is_pure_greeting:
        if user_lang == "en":
            greeting_instruction = (
                "\n[CONVERSATION DIRECTIVE: GREETING RECEIVED IN ENGLISH]\n"
                "The user greeted in English ('Hello/How are you'). "
                "Respond courteously, warmly and articulately in ENGLISH:\n"
                "- 'Hello! I am doing well. How are you, and how has your day been so far?'\n"
                "DO NOT use Urdu or Salam when the user greeted in English!\n"
            )
        else:
            greeting_instruction = (
                "\n[CONVERSATION DIRECTIVE: GREETING RECEIVED IN URDU]\n"
                "User ne aapko salam ya greeting bheji hai. "
                "Aapko mukhtasir aur ba-waqar andaaz mein salam ka jawab dena hai:\n"
                + ("- 'Wa alaikum-us-salam. Main theek hoon. Kaisi hain aap, toh phir kaisa guzra aaj ka din aapka?'\n" if user_gender == "female" else "- 'Wa alaikum-us-salam. Main theek hoon. Kaise hain aap, toh phir kaisa guzra aaj ka din aapka?'\n") +
                "STRICT BAN: Kisi bhi soorat extra lecture ya 'Boliye aaj kis uljhan ke sath aana hua...' mat bolna!\n"
            )
    elif has_greeting_word:
        if user_lang == "en":
            greeting_instruction = (
                "\n[CONVERSATION DIRECTIVE: GREETING + TOPIC IN ENGLISH]\n"
                "The user greeted in English and asked a question. Give a brief warm greeting ('Hello!') and immediately provide a deep, well-reasoned answer in English.\n"
            )
        else:
            greeting_instruction = (
                "\n[CONVERSATION DIRECTIVE: GREETING + TOPIC IN URDU]\n"
                "User ne salam ke sath topic/sawal poocha hai. Pehle 1 mukhtasir lafz mein salam ka jawab do ('Wa alaikum-us-salam.') aur foran user ke sawal ka tafseeli jawab shuru karo.\n"
            )
    else:
        if user_lang == "en":
            greeting_instruction = (
                "\n[CONVERSATION DIRECTIVE: DIRECT QUESTION IN ENGLISH (NO GREETING)]\n"
                "CRITICAL LAW: The user asked a direct question in English WITHOUT greeting. "
                "DO NOT say hello, DO NOT say salam, DO NOT ask how are you! "
                "Jump straight into an insightful, articulate and profound response in ENGLISH!\n"
            )
        else:
            greeting_instruction = (
                "\n[CONVERSATION DIRECTIVE: DIRECT TOPIC / QUESTION IN URDU (NO GREETING)]\n"
                "CRITICAL LAW: User ne salam ya greeting NAHI ki hai, balke seedha topic ya sawal poocha hai. "
                "Tumhe HARGIZ salam ka jawab nahi dena, HARGIZ 'Wa alaikum-us-salam' nahi kehna, HARGIZ 'Main theek hoon' nahi kehna, aur HARGIZ 'Kaise hain aap / kaisa guzra din' nahi bolna! "
                "SEEDHA AUR FORAN user ke sawal ka thehra hua, mukammal aur ba-waqar jawab do (bilkul ChatGPT aur Gemini ki tarah)!\n"
            )

    # Check if user is asking about Creator / Owner
    creator_triggers = [
        "kis ne banaya", "kisne banaya", "kon banaya", "kaun banaya",
        "who made you", "who created you", "who is your creator", 
        "who is your owner", "who owns you", "who developed you",
        "who designed you", "who built you",
        "tumhara owner", "tumhara creator", "owner kaun", "creator kaun",
        "owner kon", "creator kon", "kis ka bot", "kis ka chatbot",
        "kisne design kiya", "tumhe kis ne", "tumhein kisne", "tumhein kis ne",
        "tumhe kisne", "kiski creation", "tumhara malik", "tumhara maalik",
        "کس نے بنایا", "تمہیں کس نے بنایا", "اونر کون ہے", "تمہارا اونر", "کس نے بنایا ہے"
    ]
    is_creator_query = any(ct in msg_lower for ct in creator_triggers)

    creator_instruction = ""
    if is_creator_query:
        if user_lang == "en":
            creator_instruction = (
                "\n[STRICT CREATOR & OWNER MANDATE: SHANI]\n"
                "The user is asking who created, made, owns, or developed you.\n"
                "You MUST state clearly, respectfully, and authentically that you were created by SHANI, and that Shani is your creator and owner.\n"
                "For example: 'I was created by Shani. Shani is my creator and owner, who designed me as a mature, reflective AI mentor.'\n"
                "DO NOT mention Google, OpenAI, Anthropic, or any other third party as your creator. Shani is your sole creator and owner.\n"
            )
        else:
            creator_instruction = (
                "\n[STRICT CREATOR & OWNER MANDATE: SHANI]\n"
                "User aapse pooch raha hai ke aapko kisne banaya hai ya aapka owner kaun hai.\n"
                "Aapko bilkul aasan, saaf aur natural Roman Urdu mein jawab dena hai ke aapko SHANI ne banaya hai aur Shani hi aapke creator aur owner hain.\n"
                "Example response: 'Mujhe Shani ne banaya hai. Shani mere creator aur owner hain. Agar aapko kisi bhi baat par mashwara chahiye ya baat karni hai, toh batayein.'\n"
                "STRICT BAN: 'Zindagidida', 'tarasha hai', 'fikri sathi', ya aisi koi bhi mushkil ya bhaari kitaabi Urdu alfaz BILKUL use nahi karne! Alfaaz aasan aur rozmarrah bol chaal wale hon.\n"
                "Hargiz Google, OpenAI ya kisi doosri company ka naam mat lena. Shani hi aapke wahid creator aur owner hain.\n"
            )

    user_name_instruction = f"\n[USER PROFILE: Name is '{user_name}']\nAddress the user warmly by their name '{user_name}' when giving personal advice or guidance to build a genuine mentor connection.\n" if user_name and user_name.lower() != "user" else ""

    # Prepare Full System Instruction with Literary Dossiers
    full_system_instruction = (
        f"{MASTER_SYSTEM_INSTRUCTION}\n\n"
        f"--- LITERARY MASTER DOSSIERS KNOWLEDGE BASE ---\n"
        f"{compiled_knowledge}\n\n"
        f"{gender_instruction}\n"
        f"{user_name_instruction}\n"
        f"{greeting_instruction}\n"
        f"{creator_instruction}\n\n"
        "STRICT CONVERSATIONAL DIRECTIVE:\n"
        "Tumhara naam 'Amber' hai. "
        "ZABAN KA KHAAS KHYAL RAKHO: Agar Roman Urdu mein baat ho rahi hai, toh bilkul aasan, saaf aur natural Roman Urdu bolo jo aam rozmarrah bol chaal mein samajh aati ho. Bhaari, puraani, kitaabi ya mushkil khalis Urdu alfaz (jaise 'zindagidida', 'tarasha hai', 'fikri sathi', 'khisaarah' waghera) BILKUL MANA HAIN. Alfaaz ko sahi aur natural tareeqe se use karo. "
        "User ke specific sawal ko ghor se suno aur uska bar-mahal, thehra hua, authentic aur deep jawab do. "
        "IMPORTANT DIRECTIVE: Har sawal ka MUKAMMAL, mukhlis aur wazeh jawab do. Baat ko kabhi beech mein adhoora mat chhorna. Ek ba-waqar mentor ki tarah poori daleel aur naseehat ikhtitam tak bayan karo. "
        "IMAGE/VISION & FILE CAPABILITY: Agar user koi image, tasweer, HTML file (maslan shani-saylani-prep.html, khat_for_sarkar.html), text file ya dastawez attach kare, toh us file/image ke andar ke alfaz, structure aur maqsad ko bohot gehrayi se parho aur analyze karo. Uspar thehra hua, mature aur mukammal mashwara pesh karo. "
        "Koi ghisi-piti pre-made lines mat dohrao. Agar aam salam kare toh natural ba-waqar andaz mein salam ka jawab do aur baat shuru karo. "
        "Agar kisi kitab ya maslay par pooche toh apni deep knowledge se real insight do."
    )

    # Build conversation contents for Gemini
    contents = []
    for h in req.history:
        role = "user" if h.get("role") == "user" else "model"
        content = h.get("content", "")
        if content:
            contents.append({"role": role, "parts": [{"text": content}]})

    # Add current user message (with Vision & File Content support)
    user_parts = []
    if req.file_content:
        file_name = req.file_name or "uploaded_file"
        prompt_instruction = user_msg or f"Barah-e-karam is attached file '{file_name}' ko mukammal taur par parhein aur iska ba-waqar aur gehra tajziya (in-depth analysis) pesh karein."
        full_file_text = (
            f"[ATTACHED FILE: {file_name}]\n"
            f"--- FILE CONTENT START ---\n"
            f"{req.file_content}\n"
            f"--- FILE CONTENT END ---\n\n"
            f"User Query / Instruction: {prompt_instruction}"
        )
        user_parts.append({"text": full_file_text})
    else:
        prompt_text = user_msg or (
            f"Barah-e-karam is attached document '{req.file_name}' ko ghor se parhein aur iska tajziya karein." if (req.file_name and req.image_base64)
            else ("Is image ko ghor se dekhein aur iska ba-waqar tajziya ya mashwara dein." if req.image_base64 else "")
        )
        if prompt_text:
            user_parts.append({"text": prompt_text})

    if req.image_base64:
        raw_b64 = req.image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        user_parts.append({
            "inline_data": {
                "mime_type": req.image_mime_type or "image/jpeg",
                "data": raw_b64
            }
        })

    contents.append({"role": "user", "parts": user_parts})

    payload = {
        "system_instruction": {
            "parts": [{"text": full_system_instruction}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192
        }
    }

    # Candidate models in priority order
    candidate_models = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.1-pro-preview",
        "gemini-4-argon"
    ]

    last_error = ""
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, timeout=40)
            data = res.json()
            if res.status_code == 200 and "candidates" in data:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                reply_text = "".join([p.get("text", "") for p in parts if "text" in p and not p.get("thought")])
                if not reply_text:
                    reply_text = "".join([p.get("text", "") for p in parts if "text" in p])
                reply_text = reply_text.strip()
                
                # Sanitize forbidden dramatic line if generated by model
                forbidden_substrings = [
                    "Boliye, aaj kis uljhan, kis soch ya kis faisle ke sath aana hua hai? Zindagi ke kisi mor par ruke hain ya bas dil bojh-al hai? Baithein, baat karte hain.",
                    "Boliye, aaj kis uljhan, kis soch ya kis faisle ke sath aana hua hai? Zindagi ke kisi mor par ruke hain ya bas dil bojh-al hai?",
                    "Zindagi ke kisi mor par ruke hain ya bas dil bojh-al hai? Baithein, baat karte hain.",
                    "Baithein, baat karte hain."
                ]
                for fb in forbidden_substrings:
                    reply_text = reply_text.replace(fb, "").strip()
                
                # If user did NOT greet, strip any uncalled-for salam/greeting prefix from AI output
                if not has_greeting_word:
                    greeting_prefixes = [
                        "wa alaikum-us-salam. main theek hoon. kaisi hain aap, toh phir kaisa guzra aaj ka din aapka?",
                        "wa alaikum-us-salam. main theek hoon. kaise hain aap, toh phir kaisa guzra aaj ka din aapka?",
                        "wa alaikum-us-salam. main theek hoon.",
                        "wa alaikum-us-salam.",
                        "wa alaikumussalam.",
                        "wa alaikum assalam.",
                        "walaikum assalam.",
                        "salam! main theek hoon.",
                        "salam.",
                        "salam!",
                        "main theek hoon.",
                        "hello! i am doing well. how are you, and how has your day been so far?",
                        "hello! i'm doing well, thank you. how are you?",
                        "hello! i am doing well.",
                        "hello!",
                        "hello,",
                        "hi there!"
                    ]
                    clean_lower = reply_text.lower()
                    for gp in greeting_prefixes:
                        if clean_lower.startswith(gp):
                            reply_text = reply_text[len(gp):].strip()
                            clean_lower = reply_text.lower()
                
                # If user sent pure greeting, guarantee exact phrasing requested by user:
                elif is_pure_greeting:
                    if user_lang == "en":
                        # ENGLISH GREETING GUARANTEE
                        reply_text = "Hello! I am doing well. How are you, and how has your day been so far?"
                    else:
                        # ROMAN URDU GREETING GUARANTEE
                        target_phrase = "Kaisi hain aap, toh phir kaisa guzra aaj ka din aapka?" if user_gender == "female" else "Kaise hain aap, toh phir kaisa guzra aaj ka din aapka?"
                        if "kaisa guzra" not in reply_text.lower():
                            if "theek hoon" in reply_text.lower():
                                parts = reply_text.split("theek hoon", 1)
                                reply_text = f"{parts[0]}theek hoon. {target_phrase}"
                            elif "walaikum" in reply_text.lower():
                                reply_text = f"Wa alaikum-us-salam. Main theek hoon. {target_phrase}"
                            else:
                                reply_text = f"Wa alaikum-us-salam. Main theek hoon. {target_phrase}"
                
                # Creator / Owner guarantee: Ensure Shani is credited cleanly in easy, natural Roman Urdu
                if is_creator_query:
                    if "shani" not in reply_text.lower():
                        if user_lang == "en":
                            reply_text = "I was created by Shani. Shani is my creator and owner."
                        else:
                            reply_text = "Mujhe Shani ne banaya hai. Shani mere creator aur owner hain. Agar aapko kisi bhi baat par mashwara chahiye ya baat karni hai, toh batayein."
                    else:
                        # Sanitize any heavy/archaic phrases so it stays easy natural Roman Urdu
                        import re
                        heavy_replacements = [
                            (r"zindagidida aur fikri sathi ke taur par tarasha hai\.?", "design kiya hai."),
                            (r"fikri sathi ke taur par tarasha hai\.?", "design kiya hai."),
                            (r"ke taur par tarasha hai\.?", "ke liye banaya hai."),
                            (r"zindagidida", "mature"),
                            (r"fikri sathi", "mentor"),
                            (r"tarasha hai", "banaya hai")
                        ]
                        for pat, rep in heavy_replacements:
                            reply_text = re.sub(pat, rep, reply_text, flags=re.IGNORECASE).strip()

                # Save Amber reply to database for Owner monitoring
                save_message(session_id=session_id, role="model", content=reply_text, user_ip=client_ip, user_name=user_name)
                return {"reply": reply_text, "is_live_ai": True, "model": model_name}
            else:
                last_error = data.get("error", {}).get("message", res.text)
                print(f"Model {model_name} failed: {last_error}")
        except Exception as e:
            last_error = str(e)
            print(f"Exception calling {model_name}: {e}")

    # Fallback error reply
    reply_fallback = f"Maaf kijiyega, Google AI Studio server se rabte mein waqti takheer aayi hai: {last_error[:120]}..."
    save_message(session_id=session_id, role="model", content=reply_fallback, user_ip=client_ip)
    return {
        "reply": reply_fallback,
        "is_live_ai": False
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
