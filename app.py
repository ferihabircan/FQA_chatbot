import gradio as gr
import google.generativeai as genai
import os
import fitz  
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY bulunamadı. Lütfen .env dosyasını kontrol edin.")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"API Yapılandırma Hatası: {e}")
   
    api_error = str(e)


model = genai.GenerativeModel('gemini-2.0-flash-lite')

def process_uploaded_file(file):
    """
    Kullanıcının yüklediği dosyayı işler.
    Dosya PDF ise metnini çıkarır, TXT ise içeriğini okur.
    """
    if file is None:
        return None, "Lütfen bir dosya yükleyin."

    file_path = file.name
    file_extension = Path(file_path).suffix.lower()
    
    content = ""
    try:
        if file_extension == '.pdf':
            with fitz.open(file_path) as doc:
                for page in doc:
                    content += page.get_text()
        elif file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            return None, "Desteklenmeyen dosya formatı. Lütfen .pdf veya .txt uzantılı bir dosya yükleyin."
        
        if not content.strip():
             return None, "Dosya boş veya metin içeriği okunamadı."

        return content, f"✅ **{Path(file_path).name}** başarıyla işlendi. Artık sorularınızı sorabilirsiniz."
    except Exception as e:
        return None, f"Dosya işlenirken bir hata oluştu: {e}"

def generate_chat_response(message, history, document_context):
    """
    Kullanıcının sorusuna ve yüklenen dokümanın içeriğine göre cevap üretir.
    """
    if not document_context:
        return "Lütfen önce bir SSS dokümanı (.txt veya .pdf) yükleyin."

    prompt_template = f"""
    Sen, yalnızca sana aşağıda sağlanan 'DOKÜMAN' içeriğine dayanarak soruları yanıtlayan bir SSS (Sıkça Sorulan Sorular) asistanısın.
    
    GÖREVİN:
    1. Kullanıcının sorusunu dikkatlice oku.
    2. Cevabı SADECE ve SADECE aşağıdaki 'DOKÜMAN' içinde ara.
    3. Eğer cevap dokümanda mevcutsa, cevabı net ve anlaşılır bir şekilde ifade et.
    4. Eğer cevap dokümanda kesinlikle bulunmuyorsa, "Bu bilgi sağlanan dokümanda mevcut değil." veya benzeri bir ifade kullan.
    5. Kendi genel bilgini KESİNLİKLE kullanma. Sadece dokümandaki bilgilere bağlı kal.

    DOKÜMAN:
    ---
    {document_context}
    ---

    SORU:
    {message}

    CEVAP:
    """

    try:
       
        response = model.generate_content(prompt_template)
        return response.text
    except Exception as e:
        return f"Modelden cevap alınırken bir hata oluştu: {e}"


with gr.Blocks(theme=gr.themes.Soft(), title="Dinamik SSS Chatbot") as demo:
    
    document_context_state = gr.State(None)

    gr.Markdown("# 📄 Dinamik SSS Chatbot ")
    gr.Markdown(
        "Herhangi bir şirket veya konu için SSS (.txt veya .pdf) dosyasını yükleyin ve anında o konuya özel bir chatbot ile konuşmaya başlayın."
    )
    
    if 'api_error' in locals():
         gr.Markdown(f"<h3 style='color:red;'>API Yapılandırma Hatası: {api_error}</h3>")

    with gr.Row():
        with gr.Column(scale=1, min_width=300):
            gr.Markdown("### 1. Adım: Dosya Yükleyin")
            file_uploader = gr.File(
                label="SSS Dosyasını Yükle (.pdf, .txt)",
                file_types=['.pdf', '.txt']
            )
            upload_status = gr.Markdown("Dosya bekleniyor...")
        
        with gr.Column(scale=2):
            gr.Markdown("### 2. Adım: Soru Sorun")
            chatbot = gr.Chatbot(label="Sohbet", bubble_full_width=False, height=500)
            msg_textbox = gr.Textbox(label="Sorunuzu buraya yazın...", placeholder="Örn: İade politikası nedir?")
            
        
            clear_button = gr.ClearButton([msg_textbox, chatbot], value="Sohbeti Temizle")

    file_uploader.upload(
        fn=process_uploaded_file,
        inputs=[file_uploader],
        outputs=[document_context_state, upload_status]
    )

    
    def user_interaction(message, history, context):
        history.append([message, None])
        return "", history, context

    def bot_response(history, context):
        user_message = history[-1][0]
        bot_message = generate_chat_response(user_message, history, context)
        history[-1][1] = bot_message
        return history

    msg_textbox.submit(
        fn=user_interaction,
        inputs=[msg_textbox, chatbot, document_context_state],
        outputs=[msg_textbox, chatbot, document_context_state]
    ).then(
        fn=bot_response,
        inputs=[chatbot, document_context_state],
        outputs=[chatbot]
    )


if __name__ == "__main__":
    demo.launch(debug=True) 