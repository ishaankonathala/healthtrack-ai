"""HealthTrack AI 2.0 — Futuristic Medical AI Command Centre.

Phase 9 redesign: electric-teal / near-black dashboard with a genuine
interactive Three.js 3D anatomical viewer (procedural geometry via CCv2),
multi-section sidebar navigation, and all Phase 3-8 features preserved.

No real patient vitals are invented.  Demo values are clearly labelled.
No authentication is added.  No backend code is changed.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment & page config — must be first Streamlit call
# ---------------------------------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = 5
AI_REQUEST_TIMEOUT_SECONDS = 30

st.set_page_config(
    page_title="HealthTrack AI",
    page_icon=":material/ecg_heart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Lazy import requests (never at module level to avoid import-time side effects)
# ---------------------------------------------------------------------------
import requests  # noqa: E402  (after page config)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
defaults: dict[str, object] = {
    "section": "Overview",
    "ai_summaries": {},
    "rag_last_response": None,
    "api_base_url": DEFAULT_API_BASE_URL,
}
for _k, _v in defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# CCv2 — Interactive 3D Anatomy Viewer (Three.js procedural geometry)
# ---------------------------------------------------------------------------
# Declared at module level (register once, mount many times).
# No GLB file required; the model is built entirely from Three.js primitives,
# which renders instantly with zero network dependencies.
# This is an *educational geometric visualisation*, not a diagnostic tool.
# ---------------------------------------------------------------------------
_ANATOMY_HTML = """<div id="scene-root" style="width:100%;height:100%;min-height:560px;background:#080B12;border-radius:12px;overflow:hidden;position:relative;font-family:Inter,sans-serif;">
  <canvas id="c" style="display:block;width:100%;height:100%;"></canvas>

  <div style="position:absolute;top:12px;left:12px;right:12px;pointer-events:none;">
    <span style="background:rgba(0,214,197,.10);border:1px solid rgba(0,214,197,.35);border-radius:6px;padding:7px 12px;color:#00D6C5;font-size:11px;letter-spacing:1.2px;font-weight:600;">
      3D HUMAN ANATOMY ATLAS
    </span>
  </div>

  <div id="layer-panel" style="position:absolute;top:55px;left:12px;display:flex;flex-direction:column;gap:5px;max-height:390px;overflow-y:auto;background:rgba(8,11,18,.88);border:1px solid #1E2D45;border-radius:8px;padding:10px;color:#E8EDF5;font-size:11px;">
    <div style="color:#00D6C5;font-weight:700;letter-spacing:1px;margin-bottom:4px;">ANATOMICAL SYSTEMS</div>
    <label><input type="checkbox" data-layer="muscular" checked> Muscular</label>
    <label><input type="checkbox" data-layer="skeletal"> Skeletal</label>
    <label><input type="checkbox" data-layer="cardiovascular" checked> Cardiovascular</label>
    <label><input type="checkbox" data-layer="respiratory" checked> Respiratory</label>
    <label><input type="checkbox" data-layer="nervous" checked> Nervous</label>
    <label><input type="checkbox" data-layer="digestive" checked> Digestive</label>
    <label><input type="checkbox" data-layer="urinary" checked> Urinary</label>
    <label><input type="checkbox" data-layer="integumentary"> Skin</label>
    <label><input type="checkbox" data-layer="other"> Other structures</label>
  </div>

  <div style="position:absolute;bottom:14px;right:14px;display:flex;gap:8px;">
    <button id="btn-reset" style="background:rgba(0,214,197,.12);border:1px solid rgba(0,214,197,.4);color:#00D6C5;font-size:11px;padding:7px 14px;border-radius:6px;cursor:pointer;">↺ Reset camera</button>
  </div>

  <div id="spinner" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:#080B12;color:#00D6C5;font-size:13px;letter-spacing:1px;">
    Loading anatomical systems…
  </div>
  <div id="viewer-error" style="display:none;position:absolute;bottom:55px;left:12px;right:12px;background:#35131c;color:#ff9aaa;padding:10px;border-radius:6px;font-size:12px;"></div>
</div>"""

_ANATOMY_JS = r"""
export default function(component) {
  const { parentElement } = component;
  if (parentElement._anatomyInitialised) return;
  parentElement._anatomyInitialised = true;

  let disposed = false;
  let animationId = null;
  let renderer = null;
  let controls = null;

  const importMap = document.createElement('script');
  importMap.type = 'importmap';
  importMap.textContent = JSON.stringify({
    imports: {
      "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
    }
  });
  document.head.appendChild(importMap);

  const moduleScript = document.createElement('script');
  moduleScript.type = 'module';

  moduleScript.textContent = `
    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
    import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

    const root = document.querySelector('#scene-root');
    if (!root) throw new Error('Anatomy viewer root not found');

    // This module has its own scope; keep lifecycle state inside it.
    let disposed = false;
    let animationId = null;

    const canvas = root.querySelector('#c');
    const spinner = root.querySelector('#spinner');
    const errorBox = root.querySelector('#viewer-error');
    const resetButton = root.querySelector('#btn-reset');

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080B12);

    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.enablePan = true;
    controls.minDistance = 1.5;
    controls.maxDistance = 8;
    controls.maxPolarAngle = Math.PI * 0.95;

    scene.add(new THREE.HemisphereLight(0xc9e5ff, 0x17202d, 2.0));

    const keyLight = new THREE.DirectionalLight(0xffffff, 3.0);
    keyLight.position.set(3, 5, 5);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x36bfff, 2.0);
    fillLight.position.set(-4, 2, 3);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0x00d6c5, 2.0);
    rimLight.position.set(0, 3, -4);
    scene.add(rimLight);

   const floor = new THREE.GridHelper(5, 30, 0x1e2d45, 0x101722);
    floor.position.y = -0.92;
    floor.material.transparent = true;
    floor.material.opacity = 0.22;
    floor.renderOrder = -1;
    scene.add(floor);

    const modelRoot = new THREE.Group();
    scene.add(modelRoot);

    const systems = [
      'integumentary',
      'skeletal',
      'muscular',
      'cardiovascular',
      'respiratory',
      'nervous',
      'digestive',
      'urinary',
      'other'
    ];

    const initialVisibility = {
      integumentary: false,
      skeletal: false,
      muscular: true,
      cardiovascular: true,
      respiratory: true,
      nervous: true,
      digestive: true,
      urinary: true,
      other: false
    };

    const layerGroups = {};
    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);

    let loadedCount = 0;
    const totalCount = systems.length;

    function setLayerOpacity(group, opacity) {
      group.traverse((object) => {
        if (!object.isMesh) return;

        const materials = Array.isArray(object.material)
          ? object.material
          : [object.material];

        materials.forEach((material) => {
          if (!material) return;

          if (!material.userData.originalOpacity) {
            material.userData.originalOpacity =
              material.opacity === undefined ? 1 : material.opacity;
          }

          const baseOpacity = material.userData.originalOpacity;
          material.transparent = opacity < 0.999;
          material.opacity = baseOpacity * opacity;
          material.depthWrite = opacity >= 0.999;
          material.needsUpdate = true;
        });
      });
    }

    function updateVisibility() {
      systems.forEach((name) => {
        const group = layerGroups[name];
        if (!group) return;

        const checkbox = root.querySelector(
          '[data-layer="' + name + '"]'
        );

        group.visible = checkbox ? checkbox.checked : false;

        if (name === 'muscular' && group.visible) {
          setLayerOpacity(group, 0.38);
        } else if (name === 'integumentary' && group.visible) {
          setLayerOpacity(group, 0.18);
        } else {
          setLayerOpacity(group, 1);
        }
      });
    }

    root.querySelectorAll('[data-layer]').forEach((checkbox) => {
      checkbox.addEventListener('change', updateVisibility);
    });

    const defaultCenter = new THREE.Vector3(0, 0.855, 0);
    let cameraDistance = 3.5;

    function fitCamera() {
      const bounds = new THREE.Box3().setFromObject(modelRoot);
      if (bounds.isEmpty()) return;

      const center = bounds.getCenter(new THREE.Vector3());
      const size = bounds.getSize(new THREE.Vector3());

      // Center the atlas without changing relative alignment of its systems.
      modelRoot.position.sub(center);

      const centeredBounds = new THREE.Box3().setFromObject(modelRoot);
      const centeredSize = centeredBounds.getSize(new THREE.Vector3());
      const maxDimension = Math.max(
        centeredSize.x,
        centeredSize.y,
        centeredSize.z
      );

      cameraDistance = maxDimension / (
        2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))
      ) * 1.12;

      camera.position.set(0, 0.05, cameraDistance);
      controls.target.set(0, 0, 0);
      controls.minDistance = maxDimension * 0.75;
      controls.maxDistance = maxDimension * 5;
      controls.update();
    }

    function resize() {
      if (disposed) return;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (!width || !height) return;

      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(root);

    async function loadSystem(name) {
      const url = '/app/static/anatomy/' + name + '.glb';

      return new Promise((resolve, reject) => {
        loader.load(
          url,
          (gltf) => {
            if (disposed) {
              resolve();
              return;
            }

            const group = gltf.scene;
            group.name = name;

            group.traverse((object) => {
              if (!object.isMesh) return;
              object.castShadow = true;
              object.receiveShadow = true;

              // Preserve the original atlas materials and colors.
              const materials = Array.isArray(object.material)
                ? object.material
                : [object.material];

              materials.forEach((material) => {
                if (!material) return;
                material.side = THREE.DoubleSide;
              });
            });

            group.visible = initialVisibility[name];
            layerGroups[name] = group;
            modelRoot.add(group);
            resolve();
          },
          undefined,
          reject
        );
      });
    }

    async function loadAll() {
      try {
        const results = await Promise.allSettled(
          systems.map((name) => loadSystem(name))
        );

        if (disposed) return;

        const failed = results
          .map((result, index) => ({ result, name: systems[index] }))
          .filter((item) => item.result.status === 'rejected')
          .map((item) => ({
            name: item.name,
            error: item.result.reason?.message || String(item.result.reason)
          }));

        console.error('Failed anatomy models:', failed);

        const loaded = systems.length - failed.length;

        if (!loaded) {
          throw new Error(
            'No models loaded. ' +
            failed.map(item => item.name + ': ' + item.error).join(' | ')
          );
        }

        fitCamera();
        updateVisibility();
        resize();

        spinner.style.display = 'none';

        if (failed.length) {
          errorBox.style.display = 'block';
          errorBox.textContent =
            'Failed models: ' + failed.map(item => item.name + ': ' + item.error).join(' | ');
        }
      } catch (error) {
        console.error('Anatomy loading error:', error);
        spinner.style.display = 'none';
        errorBox.style.display = 'block';
        errorBox.textContent = 'Unable to load anatomy: ' + error.message;
      }
    }

    resetButton.addEventListener('click', fitCamera);

    function animate() {
      if (disposed) return;

      animationId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }

    await loadAll();
    if (!disposed) animate();

    root._anatomyDispose = () => {
      disposed = true;
      if (animationId !== null) cancelAnimationFrame(animationId);
      resizeObserver.disconnect();
      controls.dispose();

      modelRoot.traverse((object) => {
        if (!object.isMesh) return;
        object.geometry?.dispose();
o
        const materials = Array.isArray(object.material)
          ? object.material
          : [object.material];

        materials.forEach((material) => material?.dispose());
      });

      renderer.dispose();
    };
  `;

  parentElement.appendChild(moduleScript);

  return () => {
    disposed = true;
    parentElement._anatomyDispose?.();
    parentElement._anatomyInitialised = false;
  };
}
"""

_ANATOMY_VIEWER = st.components.v2.component(
    "healthtrack_anatomy_viewer",
    html=_ANATOMY_HTML,
    js=_ANATOMY_JS,
    isolate_styles=False,  # needs access to CDN scripts appended to document.head
)


def anatomy_viewer(height: int = 560) -> None:
    """Mount the Three.js anatomy viewer CCv2 component."""
    _ANATOMY_VIEWER(data={}, height=height)


# ---------------------------------------------------------------------------
# API helpers (all preserved from original)
# ---------------------------------------------------------------------------

def format_error_detail(response: requests.Response) -> str:
    """Extract a readable validation or error message from a FastAPI response."""
    try:
        payload = response.json()
    except ValueError:
        return f"Request failed with status {response.status_code}."

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(p) for p in item.get("loc", []) if p != "body")
                msg = item.get("msg", "Invalid value")
                messages.append(f"{loc}: {msg}" if loc else msg)
            else:
                messages.append(str(item))
        if messages:
            return "; ".join(messages)
    return f"Request failed with status {response.status_code}."


def format_timestamp(raw_ts: str) -> str:
    """Format an ISO-8601 timestamp for display."""
    try:
        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw_ts


def check_api_health(api_base_url: str) -> bool:
    """Check whether the FastAPI backend is reachable."""
    try:
        response = requests.get(f"{api_base_url}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def submit_symptom(
    api_base_url: str,
    patient_id: str,
    symptom_description: str,
    severity: int,
) -> tuple[bool, str]:
    """Submit a symptom log to POST /symptoms."""
    try:
        response = requests.post(
            f"{api_base_url}/symptoms",
            json={
                "patient_id": patient_id,
                "symptom_description": symptom_description,
                "severity": severity,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return False, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return False, "The request to the API timed out. Please try again."
    except requests.RequestException as exc:
        return False, f"Unexpected network error: {exc}"

    if response.status_code == 201:
        return True, "Symptom logged successfully."
    return False, format_error_detail(response)


def fetch_patient_history(
    api_base_url: str, patient_id: str
) -> tuple[list[dict] | None, str | None]:
    """Fetch symptom records for a patient from GET /symptoms/{patient_id}."""
    try:
        response = requests.get(
            f"{api_base_url}/symptoms/{patient_id}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while fetching patient history."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        records = response.json()
        records.sort(key=lambda item: item.get("timestamp", ""))
        return records, None
    return None, format_error_detail(response)


def fetch_patient_analytics(
    api_base_url: str, patient_id: str
) -> tuple[dict | None, str | None]:
    """Fetch 30-day symptom analytics from GET /analytics/{patient_id}."""
    try:
        response = requests.get(
            f"{api_base_url}/analytics/{patient_id}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while fetching patient analytics."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        return response.json(), None
    return None, format_error_detail(response)


def generate_ai_summary(
    api_base_url: str, patient_id: str
) -> tuple[dict | None, str | None]:
    """Request an AI doctor-visit summary from POST /ai/summary/{patient_id}."""
    try:
        response = requests.post(
            f"{api_base_url}/ai/summary/{patient_id}",
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while generating the AI summary. Please try again."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        return response.json(), None
    return None, format_error_detail(response)


def ask_rag_assistant(
    api_base_url: str, question: str
) -> tuple[dict | None, str | None]:
    """Send a health education question to POST /rag/ask."""
    try:
        response = requests.post(
            f"{api_base_url}/rag/ask",
            json={"question": question},
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        return None, f"Could not connect to the API at {api_base_url}. Is the backend running?"
    except requests.Timeout:
        return None, "Timed out while generating an answer. Please try again."
    except requests.RequestException as exc:
        return None, f"Unexpected network error: {exc}"

    if response.status_code == 200:
        return response.json(), None
    return None, format_error_detail(response)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def render_overview(api_base_url: str, patient_id: str) -> None:
    """3D anatomy viewer + live patient stats side-by-side."""

    col_viewer, col_stats = st.columns([3, 1], gap="medium")

    with col_viewer:
        with st.container(border=True):
            anatomy_viewer(height=560)

        st.caption(
            ":material/info: Rotate: drag · Zoom: scroll · Reset: button above. "
            "Educational geometric visualisation — not diagnostic."
        )

    with col_stats:
        st.subheader(":material/person: Patient overview")

        if not patient_id:
            st.info("Enter a patient ID in the sidebar to load data.")
        else:
            analytics, err = fetch_patient_analytics(api_base_url, patient_id)
            if err:
                st.error(err, icon=":material/error:")
            elif not analytics or analytics.get("total_entries", 0) == 0:
                st.info(f"No entries in the last 30 days for `{patient_id}`.")
            else:
                avg = analytics.get("average_severity")
                high = analytics.get("highest_severity")
                st.metric(
                    ":material/format_list_numbered: Total entries (30 d)",
                    analytics["total_entries"],
                    border=True,
                )
                st.metric(
                    ":material/show_chart: Avg severity",
                    f"{avg:.1f} / 10" if avg else "—",
                    border=True,
                )
                st.metric(
                    ":material/priority_high: Peak severity",
                    f"{high} / 10" if high else "—",
                    border=True,
                )

            # Latest entry
            records, _ = fetch_patient_history(api_base_url, patient_id)
            if records:
                latest = records[-1]
                with st.container(border=True):
                    st.caption("Latest entry")
                    st.markdown(
                        f"**{latest['symptom_description'][:120]}**"
                        f"{'…' if len(latest['symptom_description']) > 120 else ''}"
                    )
                    sev = latest["severity"]
                    sev_color = (
                        ":green[Low]" if sev <= 3
                        else ":orange[Moderate]" if sev <= 6
                        else ":red[High]"
                    )
                    st.markdown(f"Severity: **{sev}/10** — {sev_color}")
                    st.caption(format_timestamp(latest["timestamp"]))

        # API status
        with st.container(border=True):
            st.caption("API connection")
            if check_api_health(api_base_url):
                st.success("Backend connected", icon=":material/check_circle:")
            else:
                st.warning("Backend unreachable", icon=":material/warning:")


def render_symptom_tracking(api_base_url: str, patient_id: str) -> None:
    """Symptom log form + patient history table."""
    st.header(":material/edit_note: Symptom tracking")

    # Log form
    with st.container(border=True):
        st.subheader("Log a symptom")
        with st.form("symptom_submission_form", clear_on_submit=True):
            symptom_description = st.text_area(
                "Symptom description",
                placeholder="Describe the symptom in detail…",
                height=110,
            )
            severity = st.slider("Severity (1–10)", min_value=1, max_value=10, value=5)
            submitted = st.form_submit_button(
                ":material/send: Submit symptom", type="primary", width="stretch"
            )

        if submitted:
            if not patient_id:
                st.error("Enter a patient ID in the sidebar first.")
            elif not symptom_description.strip():
                st.error("Symptom description cannot be empty.")
            else:
                ok, message = submit_symptom(
                    api_base_url=api_base_url,
                    patient_id=patient_id,
                    symptom_description=symptom_description.strip(),
                    severity=severity,
                )
                if ok:
                    st.success(message, icon=":material/check:")
                else:
                    st.error(message, icon=":material/error:")

    # History table
    st.subheader(":material/history: Patient history")
    if not patient_id:
        st.info("Enter a patient ID in the sidebar to view history.")
        return

    records, error_message = fetch_patient_history(api_base_url, patient_id)
    if error_message:
        st.error(error_message)
        return
    if not records:
        st.info(f"No symptom records found for `{patient_id}`.")
        return

    table_rows = [
        {
            "Timestamp": format_timestamp(record["timestamp"]),
            "Symptom description": record["symptom_description"],
            "Severity": record["severity"],
        }
        for record in records
    ]
    df = pd.DataFrame(table_rows)
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "Severity": st.column_config.NumberColumn(
                "Severity",
                format="%d / 10",
                min_value=1,
                max_value=10,
            )
        },
        alt="Patient symptom history table",
    )


def render_analytics(api_base_url: str, patient_id: str) -> None:
    """30-day analytics metrics + ECharts trend chart."""
    st.header(":material/analytics: Symptom analytics (last 30 days)")

    if not patient_id:
        st.info("Enter a patient ID in the sidebar to view analytics.")
        return

    analytics, error_message = fetch_patient_analytics(api_base_url, patient_id)
    if error_message:
        st.error(error_message)
        return
    if not analytics or analytics.get("total_entries", 0) == 0:
        st.info(f"No symptom entries in the last 30 days for `{patient_id}`.")
        return

    # KPI row
    with st.container(horizontal=True):
        avg_sev = analytics.get("average_severity")
        high_sev = analytics.get("highest_severity")
        st.metric(
            ":material/format_list_numbered: Total entries",
            analytics["total_entries"],
            border=True,
        )
        st.metric(
            ":material/show_chart: Average severity",
            f"{avg_sev:.2f} / 10" if avg_sev is not None else "N/A",
            border=True,
        )
        st.metric(
            ":material/priority_high: Highest severity",
            f"{high_sev} / 10" if high_sev is not None else "N/A",
            border=True,
        )

    # Trend chart — interactive Plotly visualization
    daily_trend = analytics.get("daily_trend", [])
    if daily_trend:
        trend_df = pd.DataFrame(daily_trend).rename(
            columns={
                "date": "Date",
                "average_severity": "Average Severity",
                "entry_count": "Entries",
            }
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=trend_df["Date"],
                y=trend_df["Average Severity"],
                mode="lines+markers",
                name="Average severity",
                line={"color": "#00D6C5", "width": 3, "shape": "spline"},
                marker={"color": "#00D6C5", "size": 8},
                fill="tozeroy",
                fillcolor="rgba(0,214,197,0.10)",
                customdata=trend_df[["Entries"]],
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Average severity: %{y:.2f}/10<br>"
                    "Entries: %{customdata[0]}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            height=320,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 10, "r": 10, "t": 20, "b": 10},
            hovermode="x unified",
            showlegend=False,
            yaxis={
                "title": "Average severity",
                "range": [0, 10],
                "dtick": 2,
                "gridcolor": "#1E2D45",
            },
            xaxis={
                "title": None,
                "gridcolor": "#0D1826",
            },
            font={"color": "#A9B8CC"},
        )

        with st.container(border=True):
            st.subheader("Daily average severity trend")
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": True, "scrollZoom": True},
            )


def render_ai_summary(api_base_url: str, patient_id: str) -> None:
    """On-demand AI doctor-visit summary (never auto-called)."""
    st.header(":material/smart_toy: AI doctor-visit summary")

    with st.container(border=True):
        st.markdown(
            "Generate a **non-diagnostic** summary of recorded symptoms to share with your clinician. "
            "This sends the patient's symptom history to the **Google Gemini API**. "
            "Use only synthetic / demo data."
        )

        if not patient_id:
            st.warning("Enter a patient ID in the sidebar first.")
            return

        summaries_by_patient: dict = st.session_state.setdefault("ai_summaries", {})

        if st.button(
            ":material/send: Generate summary",
            type="primary",
            key=f"generate_summary_{patient_id}",
        ):
            with st.spinner("Generating doctor-visit summary via Gemini…"):
                summary_data, error_message = generate_ai_summary(api_base_url, patient_id)
            if error_message:
                st.error(error_message)
            elif summary_data:
                summaries_by_patient[patient_id] = summary_data

        cached_summary = summaries_by_patient.get(patient_id)
        if cached_summary:
            with st.container(border=True):
                st.markdown(cached_summary["summary"])
            st.caption(
                f"Based on {cached_summary['entry_count']} recorded entries · "
                f"Model: {cached_summary['model']} · {cached_summary['disclaimer']}"
            )


def render_rag_assistant(api_base_url: str) -> None:
    """RAG-grounded health education Q&A."""
    st.header(":material/school: Health education assistant")

    with st.container(border=True):
        st.caption(
            "Ask general health education questions grounded in curated MedlinePlus resources. "
            "This is **not** a diagnostic tool. Topics: headache, fever, dehydration, common cold."
        )

        question_input = st.text_input(
            "Health education question",
            placeholder="e.g. What are common signs of dehydration?",
            key="rag_question_input",
            label_visibility="collapsed",
        )

        if st.button(":material/search: Ask", type="primary", key="rag_ask_button"):
            cleaned_question = question_input.strip()
            if not cleaned_question:
                st.error("Please enter a question before clicking Ask.")
            else:
                with st.spinner("Searching health education resources…"):
                    rag_data, error_message = ask_rag_assistant(api_base_url, cleaned_question)
                if error_message:
                    st.error(error_message)
                elif rag_data:
                    st.session_state["rag_last_response"] = rag_data

    last_response = st.session_state.get("rag_last_response")
    if last_response:
        with st.container(border=True):
            st.markdown(last_response["answer"])
        sources = last_response.get("sources", [])
        if sources:
            st.markdown("**Sources**")
            for src in sources:
                title = src.get("title", "Source")
                url = src.get("url", "")
                if url:
                    st.markdown(f"- [{title}]({url})")
                else:
                    st.markdown(f"- {title}")
        else:
            st.info("No matching knowledge base sources were cited for this response.")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> tuple[str, str, str]:
    """Render sidebar navigation and config. Returns (section, patient_id, api_base_url)."""
    with st.sidebar:
        # Logo / branding
        st.markdown(
            "## :material/ecg_heart: HealthTrack AI",
        )
        st.caption("Intelligent symptom monitoring & consultation assistant")
        st.divider()

        # Navigation
        section = st.segmented_control(
            "Navigate",
            options=["Overview", "Symptom tracking", "Analytics", "AI summary", "Health education"],
            default="Overview",
            key="nav_section",
            label_visibility="collapsed",
        )
        if section is None:
            section = "Overview"
        st.session_state["section"] = section

        st.divider()

        # Patient ID
        st.markdown("**Patient**")
        patient_id_input = st.text_input(
            "Patient ID",
            placeholder="e.g. patient-001",
            label_visibility="collapsed",
            key="sidebar_patient_id",
        )
        patient_id = patient_id_input.strip()

        st.divider()

        # API config
        st.markdown("**Backend**")
        api_url_input = st.text_input(
            "API base URL",
            value=st.session_state["api_base_url"],
            label_visibility="collapsed",
            key="sidebar_api_url",
        )
        api_base_url = (api_url_input.strip() or DEFAULT_API_BASE_URL).rstrip("/")
        st.session_state["api_base_url"] = api_base_url

        # Health indicator
        if check_api_health(api_base_url):
            st.success("API connected", icon=":material/check_circle:")
        else:
            st.warning("API unreachable", icon=":material/wifi_off:")

        st.divider()

        # Footer / disclaimer
        st.caption(
            "⚠ This prototype contains **no authentication**. "
            "Use only synthetic test data. "
            "Not for production or real patient data."
        )

    return section, patient_id, api_base_url


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    section, patient_id, api_base_url = render_sidebar()

    if section == "Overview":
        render_overview(api_base_url, patient_id)
    elif section == "Symptom tracking":
        render_symptom_tracking(api_base_url, patient_id)
    elif section == "Analytics":
        render_analytics(api_base_url, patient_id)
    elif section == "AI summary":
        render_ai_summary(api_base_url, patient_id)
    elif section == "Health education":
        render_rag_assistant(api_base_url)


if __name__ == "__main__":
    main()
