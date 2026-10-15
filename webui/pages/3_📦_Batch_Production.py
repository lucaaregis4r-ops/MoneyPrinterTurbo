"""Batch Production & Render Queue — Fábrica de Shorts (Streamlit UI).

Upload multiple human scripts, monitor queue status in real time, and organize final exports by channel.
"""

from pathlib import Path
import streamlit as st

from app.services.batch.batch_manager import BatchManager
from app.services.batch.export_organizer import ExportOrganizer
from app.services.batch.job_queue import JobQueue, JobStatus
from app.services.batch.worker import BatchWorker
from app.services.factory import ShortsFactory

st.set_page_config(
    page_title="Fila de Produção em Lote — Fábrica de Shorts",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Fila de Produção em Lote (Batch Production)")
st.caption(
    "Adicione dezenas de roteiros humanos em lote, processe a fila de renderização em segundo plano "
    "e receba seus vídeos 9:16 organizados automaticamente por canal e data."
)

# Initialize services
queue = JobQueue()
organizer = ExportOrganizer()
manager = BatchManager(queue=queue)
worker = BatchWorker(queue=queue, organizer=organizer)

# Top Metrics Row
stats = queue.get_queue_stats()
col_m1, col_m2, col_m3, col_m4, col_ctrl = st.columns([1, 1, 1, 1, 1.5])

with col_m1:
    st.metric("Total de Jobs", stats["total"])
with col_m2:
    st.metric("Na Fila (Pending)", stats["pending"])
with col_m3:
    st.metric("Em Produção", stats["processing"])
with col_m4:
    completed_txt = f"{stats['completed']} ok"
    if stats["failed"] > 0:
        completed_txt += f" ({stats['failed']} falhas)"
    st.metric("Concluídos", completed_txt)

with col_ctrl:
    st.write("**Controles da Fila:**")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("▶️ Processar Próximo", use_container_width=True):
            with st.spinner("Processando job da fila..."):
                processed = worker.process_one()
                if processed:
                    st.success(f"Job {processed.title} finalizado com sucesso!")
                else:
                    st.info("Nenhum job pendente na fila.")
                st.rerun()

    with btn_col2:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.rerun()

st.divider()

# Tabs
tab_new, tab_queue, tab_exports = st.tabs([
    "📥 Inserir Roteiros em Massa",
    "📋 Acompanhar Fila de Produção",
    "📁 Arquivo de Exportações",
])

# ==========================================
# TAB 1: INGESTÃO EM MASSA
# ==========================================
with tab_new:
    st.subheader("Ingestão de Múltiplos Roteiros")
    st.caption("Você pode colar um documento com vários roteiros separados por '---' ou fazer upload de arquivos .md/.txt.")

    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    with col_cfg1:
        default_channel = st.selectbox(
            "Canal Padrão:",
            ["fisica", "esportes", "historia", "curiosidades", "geral"],
            index=0,
        )
    with col_cfg2:
        default_voice = st.selectbox(
            "Voz Padrão:",
            ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", "pt-BR-ThalitaNeural"],
            index=0,
        )
    with col_cfg3:
        priority_val = st.number_input("Prioridade da Carga:", min_value=0, max_value=10, value=0)

    input_mode = st.radio("Modo de Entrada:", ["Colar Documento com Múltiplos Roteiros", "Upload de Arquivos (.md / .txt)"], horizontal=True)

    if input_mode == "Colar Documento com Múltiplos Roteiros":
        example_template = (
            "# Por que a Força Depende da Massa?\n"
            "[channel: fisica]\n"
            "Você provavelmente aprendeu que força é massa vezes aceleração. [visual: formula F = m * a]\n"
            "Mas o que isso quer dizer na prática? Imagine empurrar um carrinho de compras vazio.\n"
            "Com um empurrão leve ele voa longe. Agora coloque cinquenta quilos de carga.\n"
            "Você precisa de muito mais esforço para atingir a mesma aceleração.\n"
            "---\n"
            "# A Velocidade Humana no Limite\n"
            "[channel: esportes]\n"
            "Em 2009 Usain Bolt atingiu impressionantes 44 km/h na final dos 100 metros rasos.\n"
            "Nenhum ser humano jamais se moveu tão rápido com as próprias pernas na história registrada.\n"
            "O mais impressionante é que ele desacelerou nos últimos dez metros comemorando.\n"
        )

        batch_text = st.text_area(
            "Conteúdo dos Roteiros (separe cada roteiro com '---'):",
            value=example_template,
            height=280,
        )

        if st.button("🚀 Enfileirar Roteiros para Produção", type="primary"):
            if not batch_text.strip():
                st.error("Cole pelo menos um roteiro antes de continuar.")
            else:
                jobs = manager.ingest_multi_script_text(
                    text=batch_text,
                    default_channel=default_channel,
                    default_voice=default_voice,
                    priority=int(priority_val),
                )
                if jobs:
                    st.success(f"{len(jobs)} roteiro(s) enfileirados com sucesso na Fila de Produção!")
                    st.rerun()
                else:
                    st.warning("Nenhum roteiro válido foi encontrado no texto fornecido (verifique se os textos têm mais de 20 caracteres).")

    else:
        uploaded_files = st.file_uploader(
            "Selecione arquivos de roteiro (.md ou .txt):",
            type=["md", "txt"],
            accept_multiple_files=True,
        )

        if uploaded_files and st.button("🚀 Enfileirar Arquivos Carregados", type="primary"):
            enqueued_count = 0
            for uploaded in uploaded_files:
                text_content = uploaded.read().decode("utf-8")
                jobs = manager.ingest_multi_script_text(
                    text=text_content,
                    default_channel=default_channel,
                    default_voice=default_voice,
                    priority=int(priority_val),
                )
                enqueued_count += len(jobs)

            if enqueued_count > 0:
                st.success(f"{enqueued_count} roteiro(s) de {len(uploaded_files)} arquivo(s) foram enfileirados com sucesso!")
                st.rerun()
            else:
                st.warning("Não foi possível extrair roteiros dos arquivos enviados.")

# ==========================================
# TAB 2: FILA DE PRODUÇÃO
# ==========================================
with tab_queue:
    st.subheader("Status da Fila de Produção")

    col_flt1, col_flt2 = st.columns([1, 2])
    with col_flt1:
        filter_status = st.selectbox(
            "Filtrar por Status:",
            ["Todos", JobStatus.PENDING.value, JobStatus.PROCESSING.value, JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value],
            index=0,
        )

    status_arg = None if filter_status == "Todos" else filter_status
    jobs = queue.list_jobs(status=status_arg, limit=100)

    if not jobs:
        st.info("Nenhum job encontrado com os filtros selecionados.")
    else:
        for job in jobs:
            # Status icon and styling
            if job.status == JobStatus.COMPLETED.value:
                badge = "✅ CONCLUÍDO"
                border_color = "#10b981"
            elif job.status == JobStatus.PROCESSING.value:
                badge = "⚙️ EM PRODUÇÃO"
                border_color = "#3b82f6"
            elif job.status == JobStatus.FAILED.value:
                badge = "❌ FALHOU"
                border_color = "#ef4444"
            elif job.status == JobStatus.CANCELLED.value:
                badge = "🚫 CANCELADO"
                border_color = "#6b7280"
            else:
                badge = "⏳ AGUARDANDO"
                border_color = "#f59e0b"

            with st.expander(f"{badge}  |  **{job.title}**  (Canal: {job.channel})  —  {job.created_at[:16]}"):
                c1, c2 = st.columns([2, 1])

                with c1:
                    st.write(f"**ID do Job:** `{job.job_id}` | **Voz:** `{job.voice_name or 'padrão'}`")
                    st.write(f"**Status:** {job.progress_message}")
                    if job.status == JobStatus.PROCESSING.value:
                        st.progress(max(0.05, min(1.0, job.progress)))
                    elif job.status == JobStatus.COMPLETED.value:
                        st.progress(1.0)

                    if job.error_message:
                        st.error(f"Erro detalhado:\n```\n{job.error_message}\n```")

                    with st.expander("Ver Texto do Roteiro"):
                        st.text(job.script_text)

                with c2:
                    st.write("**Ações:**")
                    if job.status in {JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                        if st.button("🔁 Re-tentar Job", key=f"retry_{job.job_id}"):
                            queue.retry_job(job.job_id)
                            st.rerun()

                    if job.status in {JobStatus.PENDING.value, JobStatus.PROCESSING.value}:
                        if st.button("🛑 Cancelar Job", key=f"cancel_{job.job_id}"):
                            queue.cancel_job(job.job_id)
                            st.rerun()

                    if st.button("🗑️ Excluir da Fila", key=f"del_{job.job_id}"):
                        queue.delete_job(job.job_id)
                        st.rerun()

                    if job.status == JobStatus.COMPLETED.value and job.exported_path:
                        exp_p = Path(job.exported_path)
                        if exp_p.exists():
                            with open(exp_p, "rb") as vf:
                                st.download_button(
                                    "⬇️ Baixar Vídeo MP4",
                                    data=vf.read(),
                                    file_name=exp_p.name,
                                    mime="video/mp4",
                                    key=f"dl_{job.job_id}",
                                )

# ==========================================
# TAB 3: ARQUIVO DE EXPORTAÇÕES
# ==========================================
with tab_exports:
    st.subheader("Arquivo de Vídeos Exportados")
    st.caption("Todos os vídeos finalizados e organizados por canal com metadados prontos para publicação.")

    ch_filter = st.selectbox("Filtrar Exportações por Canal:", ["Todos", "fisica", "esportes", "historia", "curiosidades"], index=0)
    sel_channel = None if ch_filter == "Todos" else ch_filter
    exports = organizer.list_exports(channel=sel_channel)

    if not exports:
        st.info("Nenhum vídeo exportado ainda nesta pasta.")
    else:
        st.write(f"Total de vídeos exportados encontrados: **{len(exports)}**")
        for item in exports:
            with st.container():
                c_vid, c_info = st.columns([1, 1.5])
                with c_vid:
                    mp4_path = Path(item["video_path"])
                    if mp4_path.exists():
                        st.video(str(mp4_path))
                    else:
                        st.warning("Arquivo de vídeo não encontrado no caminho original.")

                with c_info:
                    st.markdown(f"### {item.get('title')}")
                    st.write(f"📁 **Canal:** `{item.get('channel')}`  |  ⏱️ **Duração:** `{item.get('duration_seconds')}s`  |  🎬 **Cenas:** `{item.get('total_scenes')}`")
                    st.write(f"🏷️ **Hashtags:** {' '.join(item.get('hashtags', []))}")

                    with st.expander("Copiar Descrição Pronta para YouTube Shorts / TikTok"):
                        st.text_area("Descrição:", value=item.get("suggested_description", ""), height=100, key=f"desc_{item.get('video_file')}")

                    if mp4_path.exists():
                        with open(mp4_path, "rb") as f:
                            st.download_button(
                                "⬇️ Baixar Vídeo (.mp4)",
                                data=f.read(),
                                file_name=mp4_path.name,
                                mime="video/mp4",
                                key=f"dl_exp_{item.get('video_file')}",
                            )
                st.divider()
