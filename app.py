import gradio as gr
import google.generativeai as genai
import os
import fitz  # PyMuPDF
import docx  # python-docx
from PIL import Image # Pillow
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration and Setup ---
load_dotenv()

try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY bulunamadı. Lütfen .env dosyasını kontrol edin.")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"API Yapılandırma Hatası: {e}")
    api_error = str(e)

# IMPORTANT: We are updating the model to one that supports multimodal (text + image) input.
# 'gemini-1.5-flash-latest' is perfect for this.
model = genai.GenerativeModel('gemini-2.5-pro')

# --- File Processing Logic ---
def process_uploaded_file(file):
    """
    Kullanıcının yüklediği dosyayı işler.
    - PDF, DOCX, TXT: Metin içeriğini çıkarır.
    - Image: Görüntü nesnesini döndürür.
    """
    if file is None:
        return None, "Lütfen bir dosya yükleyin."

    # Gradio'nun oluşturduğu geçici dosyanın yolunu alıyoruz.
    # Bu yöntem, 'NamedString' hatasını önler ve en güvenilir yoldur.
    file_path = file.name
    file_extension = Path(file_path).suffix.lower()
    
    try:
        content = None
        if file_extension == '.pdf':
            text_content = ""
            # DÜZELTME BURADA: Dosyayı doğrudan 'file_path' kullanarak açıyoruz.
            with fitz.open(file_path) as doc:
                for page in doc:
                    text_content += page.get_text()
            content = text_content
            
        elif file_extension == '.txt':
            # .txt dosyaları için de dosya yolunu kullanmak tutarlıdır.
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
        elif file_extension == '.docx':
            # .docx dosyaları için de dosya yolu kullanılır.
            doc = docx.Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            content = '\n'.join(full_text)
            
        elif file_extension in ['.png', '.jpg', '.jpeg', '.webp']:
            # Resimler için de dosya yolu kullanılır.
            content = Image.open(file_path)
            
        else:
            return None, "Desteklenmeyen format. Lütfen .pdf, .txt, .docx, .png, .jpg uzantılı dosya yükleyin."
        
        # Metin içeriğinin boş olup olmadığını kontrol et
        if isinstance(content, str) and not content.strip():
            return None, "Dosya boş veya metin içeriği okunamadı."
        
        # İçeriğin başarıyla işlendiğinden emin ol
        if content is None:
             return None, "Dosya işlenemedi."

        return content, f"✅ **{Path(file_path).name}** başarıyla işlendi. Artık sorularınızı sorabilirsiniz."
    
    except Exception as e:
        return None, f"Dosya işlenirken bir hata oluştu: {e}"
  

# --- Chat Response Generation ---
def generate_chat_response(message, history, document_context):
    """
    Kullanıcının sorusuna ve yüklenen dokümanın (metin VEYA resim) içeriğine göre cevap üretir.
    """
    if not document_context:
        return "Lütfen önce bir doküman (.txt, .pdf, .docx, .png, .jpg) yükleyin."

    try:
        # Case 1: The context is TEXT (from PDF, DOCX, TXT)
        if isinstance(document_context, str):
            prompt = f"""
            Sen, yalnızca sana aşağıda sağlanan 'DOKÜMAN' içeriğine dayanarak soruları yanıtlayan bir SSS (Sıkça Sorulan Sorular) asistanısın.
            
            GÖREVİN:
            1. Kullanıcının sorusunu dikkatlice oku.
            2. Cevabı SADECE ve SADECE aşağıdaki 'DOKÜMAN' içinde ara.
            3. Eğer cevap dokümanda mevcutsa, cevabı net ve anlaşılır bir şekilde ifade et.
            4. Eğer cevap dokümanda kesinlikle bulunmuyorsa, "Sorularınız için canlı desteğe yönlendiriliyorsunuz" veya benzeri bir ifade kullan.
            5. Kendi genel bilgini KESİNLİKLE kullanma. Sadece dokümandaki bilgilere bağlı kal.

            DOKÜMAN:
            ---
            {document_context}
            ---

            SORU: {message}
            CEVAP:
            """
            # Generate content from text-only prompt
            response = model.generate_content(prompt)
        
        # Case 2: The context is an IMAGE
        elif isinstance(document_context, Image.Image):
            prompt = f"""
            Sen, yalnızca sana sağlanan 'GÖRÜNTÜ'yü analiz eden bir görsel asistansın.
            Görevin, kullanıcının sorduğu soruyu SADECE bu görüntüye bakarak cevaplamaktır.
            Görüntünün dışından herhangi bir bilgi kullanma.
            
            SORU: {message}
            CEVAP:
            """
            # For multimodal input, pass a list containing the text prompt and the image
            response = model.generate_content([prompt, document_context])
        
        else:
            return "İşlenemeyen bir doküman formatı ile karşılaşıldı."

        return response.text
    except Exception as e:
        return f"Modelden cevap alınırken bir hata oluştu: {e}"


# --- Gradio UI ---
with gr.Blocks(theme=gr.themes.Soft(), title="Dinamik SSS Chatbot") as demo:
    
    document_context_state = gr.State(None)

    gr.Markdown("# 📄 Gelişmiş Dinamik Chatbot ")
    gr.Markdown(
        "Herhangi bir şirket veya konu için doküman (.txt, .pdf, .docx) veya görsel (.png, .jpg) yükleyin ve anında o konuya özel bir chatbot ile konuşmaya başlayın."
    )
    
    if 'api_error' in locals():
         gr.Markdown(f"<h3 style='color:red;'>API Yapılandırma Hatası: {api_error}</h3>")

    with gr.Row():
        with gr.Column(scale=1, min_width=300):
            gr.Markdown("### 1. Adım: Dosya Yükleyin")
            file_uploader = gr.File(
                label="Doküman veya Görsel Yükle",
                file_types=['.pdf', '.txt', '.docx', '.png', '.jpg', '.jpeg'] # Updated file types
            )
            upload_status = gr.Markdown("Dosya bekleniyor...")
        
        with gr.Column(scale=2):
            gr.Markdown("### 2. Adım: Soru Sorun")
            chatbot = gr.Chatbot(label="Sohbet", bubble_full_width=False, height=500)
            msg_textbox = gr.Textbox(label="Sorunuzu buraya yazın...", placeholder="Örn: İade politikası nedir? / Bu resimde ne görüyorsun?")
            clear_button = gr.ClearButton([msg_textbox, chatbot], value="Sohbeti Temizle")

    # --- Event Handlers ---
    file_uploader.upload(
        fn=process_uploaded_file,
        inputs=[file_uploader],
        outputs=[document_context_state, upload_status]
    )

    def user_interaction(message, history):
        # We don't need to pass the context here, it's handled by the `bot_response` function
        history.append([message, None])
        return "", history

    def bot_response(history, context):
        user_message = history[-1][0]
        bot_message = generate_chat_response(user_message, history, context)
        history[-1][1] = bot_message
        return history

    # Chain of events for chat submission
    msg_textbox.submit(
        fn=user_interaction,
        inputs=[msg_textbox, chatbot],
        outputs=[msg_textbox, chatbot]
    ).then(
        fn=bot_response,
        inputs=[chatbot, document_context_state],
        outputs=[chatbot]
    )


if __name__ == "__main__":
    demo.launch(debug=True)