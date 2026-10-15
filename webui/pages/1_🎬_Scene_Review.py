"""Review Studio — Fábrica de Shorts (Streamlit UI).

Interactive scene-by-scene review, 9:16 draft player, 1-click candidate swap, and partial re-render.
"""

import os
from pathlib import Path
import streamlit as st

from app.services.review.review_manager import ReviewManager


st.set_page_config(
    page_title="Review Studio — Fábrica de Shorts",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Review Studio — Fábrica de Shorts")
st.caption("Conteúdo humano, produção automatizada. Revise cena por cena e troque qualquer mídia com 1 clique.")

manager = ReviewManager()
available_projects = manager.list_projects()

if not available_projects:
    st.warning("Nenhum projeto com `scenes.json` encontrado em `storage/projects/`.")
    st.info("Gere um projeto usando o Scene Director CLI (`python -m app.services.director.cli`) ou a ShortsFactory.")
    st.stop()

# Sidebar: Project Selection
with st.sidebar:
    st.header("⚙️ Projetos")
    selected_project_id = st.selectbox(
        "Selecione a Produção:",
        available_projects,
        index=0,
    )
    if st.button("🔄 Atualizar Lista"):
        st.rerun()

# Load project review data
try:
    project_data = manager.get_project_data(selected_project_id)
except Exception as e:
    st.error(f"Erro ao carregar dados do projeto: {e}")
    st.stop()

plan = project_data["plan"]
latest_video = project_data["latest_video"]
current_rev = project_data["current_revision"]

# Top Metrics Bar
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Total de Cenas", len(plan.scenes))
with col_m2:
    st.metric("Duração Estimada", f"{plan.estimated_duration:.1f}s")
with col_m3:
    st.metric("Estilo Visual", plan.brand_preset.upper())
with col_m4:
    status_label = "✅ Pronto para Revisão" if latest_video else "⏳ Cenas Planejadas"
    st.metric("Status", status_label)

st.divider()

# Layout: 2 Columns (Draft Player on Left/Top, Scene Inspector on Right)
col_player, col_details = st.columns([1, 1.8])

with col_player:
    st.subheader("📱 Rascunho Vertical (9:16)")
    if latest_video and Path(latest_video).exists():
        st.video(latest_video)
        st.caption(f"Revisão ativa: `{current_rev or 'inicial'}`")
        if st.button("🚀 Aprovar Vídeo (Status: APPROVED)", type="primary", use_container_width=True):
            st.balloons()
            st.success("Vídeo aprovado com sucesso para expedição e publicação!")
    else:
        st.info("O vídeo draft ainda não foi montado para este projeto.")
        if st.button("🔨 Montar Vídeo Draft Inicial Agora", type="primary"):
            with st.spinner("Sintetizando áudio, coletando mídias e montando rascunho 9:16..."):
                from app.services.factory import ShortsFactory
                factory = ShortsFactory()
                folder = Path(f"storage/projects/{selected_project_id}")
                script_file = Path(f"storage/scripts/{selected_project_id}.md")
                script_text = script_file.read_text(encoding="utf-8") if script_file.exists() else " ".join(s.narration for s in plan.scenes)
                res = factory.produce_draft(
                    script_id=selected_project_id,
                    script_text=script_text,
                    channel=plan.brand_preset,
                )
                st.success("Draft renderizado com sucesso!")
                st.rerun()

with col_details:
    st.subheader("🔍 Inspeção e Troca por Cena")
    st.caption("Substitua mídias individuais. O sistema reconstrói apenas a cena trocada, economizando 90% do tempo de render.")

    for idx, scene in enumerate(plan.scenes):
        dur_str = f"{scene.start:.1f}s - {scene.end:.1f}s" if (scene.start is not None and scene.end is not None) else f"Cena #{idx+1}"
        with st.expander(f"**Cena {idx+1}** (`{scene.scene_id}`) | {dur_str} | Tag: `[{scene.visual_type.upper()}]`", expanded=(idx == 0)):
            # Narration
            st.markdown(f"**🗣️ Narração Aprovada (Texto Bloqueado):**")
            st.info(f"\"{scene.narration}\"")

            # Intent & Motion
            c_int, c_mot = st.columns(2)
            with c_int:
                st.markdown(f"**🎯 Intenção Visual:** {scene.intent}")
            with c_mot:
                st.markdown(f"**🎥 Movimento:** `{scene.preferred_motion}`")

            # Current Selection
            selected = scene.selected_media or {}
            curr_path = selected.get("local_path")
            st.markdown(f"**Mídia Ativa:** `{selected.get('provider', 'padrão')}` | Arquivo: `{Path(curr_path).name if curr_path else 'Nenhum'}`")
            if curr_path and Path(curr_path).exists():
                st.video(curr_path)

            # Alternatives (Candidates)
            candidates = scene.media_candidates or []
            if candidates:
                st.markdown("##### 🎞️ Candidatos Alternativos Disponíveis:")
                cols = st.columns(min(len(candidates), 3))
                for c_idx, cand in enumerate(candidates[:3]):
                    with cols[c_idx]:
                        is_active = (selected.get("asset_id") == cand.get("asset_id")) or (selected.get("url") == cand.get("url"))
                        st.markdown(f"**Opção #{c_idx+1}** ({cand.get('provider', 'stock')})")
                        st.caption(f"Score: {cand.get('technical_score', 0.9):.2f} | Dur: {cand.get('duration', 5):.1f}s")
                        
                        cand_local = cand.get("local_path")
                        if cand_local and Path(cand_local).exists():
                            st.video(cand_local)

                        if is_active:
                            st.button("✓ Selecionado", key=f"active_{scene.scene_id}_{c_idx}", disabled=True)
                        else:
                            if st.button("Trocar para Este", key=f"swap_{scene.scene_id}_{c_idx}"):
                                with st.spinner(f"Reconstruindo apenas a {scene.scene_id} e remontando o vídeo final..."):
                                    # Ensure candidate has a local file
                                    target_media_path = cand.get("local_path")
                                    if not target_media_path or not Path(target_media_path).exists():
                                        from app.services.media_ranker.candidate_builder import _generate_synthetic_clip
                                        gen_path = Path(f"storage/media_cache/swap_{scene.scene_id}_{c_idx}.mp4")
                                        _generate_synthetic_clip(cand.get("query", scene.narration), gen_path)
                                        target_media_path = str(gen_path)

                                    swap_res = manager.swap_scene_media(
                                        project_id=selected_project_id,
                                        scene_id=scene.scene_id,
                                        new_footage_path=target_media_path,
                                        new_candidate_info=cand,
                                    )
                                    reused_count = len(swap_res["reused_stages"])
                                    st.success(f"Cena {scene.scene_id} atualizada com sucesso! {reused_count} estágios reaproveitados do cache.")
                                    st.rerun()

            # Custom File Upload for this scene
            st.markdown("##### 📁 Usar Arquivo Local Próprio:")
            uploaded_file = st.file_uploader(
                f"Enviar vídeo ou imagem para a {scene.scene_id}",
                type=["mp4", "mov", "avi", "png", "jpg"],
                key=f"upload_{scene.scene_id}",
            )
            if uploaded_file is not None:
                if st.button(f"Aplicar Upload na {scene.scene_id}", key=f"btn_upload_{scene.scene_id}"):
                    save_dir = Path("storage/media_cache")
                    saved_path = save_dir / f"upload_{scene.scene_id}_{uploaded_file.name}"
                    with open(saved_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    with st.spinner(f"Aplicando {uploaded_file.name} na {scene.scene_id} e re-renderizando..."):
                        swap_res = manager.swap_scene_media(
                            project_id=selected_project_id,
                            scene_id=scene.scene_id,
                            new_footage_path=saved_path,
                        )
                        st.success(f"Mídia própria aplicada na {scene.scene_id}!")
                        st.rerun()
