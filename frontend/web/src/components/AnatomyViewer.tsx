import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type AtlasManifest = {
  bounds: { min: [number, number, number]; max: [number, number, number] }
}

type ViewerRuntime = {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer
  controls: OrbitControls
  loader: GLTFLoader
  modelRoot: THREE.Group
  center: THREE.Vector3 | null
  requestId: number
  currentModel: THREE.Group | null
  disposed: boolean
  animationFrame: number
  resizeObserver: ResizeObserver | null
}

type ViewerStatus = 'loading-manifest' | 'loading-model' | 'loaded' | 'error'

function disposeModel(model: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>()
  const materials = new Set<THREE.Material>()
  const textures = new Set<THREE.Texture>()

  model.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return
    geometries.add(object.geometry)
    const objectMaterials = Array.isArray(object.material) ? object.material : [object.material]
    objectMaterials.forEach((material) => {
      materials.add(material)
      Object.values(material).forEach((value) => {
        if (value instanceof THREE.Texture) textures.add(value)
      })
    })
  })

  geometries.forEach((geometry) => geometry.dispose())
  materials.forEach((material) => material.dispose())
  textures.forEach((texture) => texture.dispose())
}

function readManifestBounds(manifest: AtlasManifest) {
  const { min, max } = manifest.bounds
  if (
    !Array.isArray(min) || !Array.isArray(max) || min.length !== 3 || max.length !== 3 ||
    [...min, ...max].some((value) => !Number.isFinite(value))
  ) throw new Error('The anatomy manifest does not contain valid 3D bounds.')

  const minPoint = new THREE.Vector3(...min)
  const maxPoint = new THREE.Vector3(...max)
  const bounds = new THREE.Box3(minPoint, maxPoint)
  const center = bounds.getCenter(new THREE.Vector3())
  const size = bounds.getSize(new THREE.Vector3())
  const radius = size.length() / 2
  return { center, radius }
}

export default function AnatomyViewer({ selectedSystem }: { selectedSystem: string }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const runtimeRef = useRef<ViewerRuntime | null>(null)
  const [manifestReady, setManifestReady] = useState(false)
  const [retryVersion, setRetryVersion] = useState(0)
  const [manifestRetryVersion, setManifestRetryVersion] = useState(0)
  const [status, setStatus] = useState<ViewerStatus>('loading-manifest')
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    let disposed = false
    const manifestController = new AbortController()
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100)
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' })
    } catch (rendererError) {
      setError(rendererError instanceof Error ? `WebGL could not start: ${rendererError.message}` : 'WebGL could not start in this browser.')
      setStatus('error')
      return () => { disposed = true; manifestController.abort() }
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.12
    renderer.setClearColor(0x000000, 0)
    renderer.domElement.className = 'anatomy-canvas'
    renderer.domElement.setAttribute('aria-label', 'Interactive 3D anatomy model')
    host.prepend(renderer.domElement)

    scene.add(new THREE.HemisphereLight(0xd9f2ff, 0x1b2630, 1.55))
    const keyLight = new THREE.DirectionalLight(0xf1fbff, 2.0)
    keyLight.position.set(2.5, 4.5, 4)
    scene.add(keyLight)
    const fillLight = new THREE.DirectionalLight(0x55daca, 0.65)
    fillLight.position.set(-3.2, 1.3, 2.4)
    scene.add(fillLight)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.075
    controls.rotateSpeed = 0.65
    controls.zoomSpeed = 0.8
    controls.enablePan = true
    controls.minDistance = 1.5
    controls.maxDistance = 8.5
    controls.maxPolarAngle = Math.PI * 0.98

    const loader = new GLTFLoader()
    loader.setMeshoptDecoder(MeshoptDecoder)
    const modelRoot = new THREE.Group()
    modelRoot.name = 'selected-anatomy-system'
    scene.add(modelRoot)

    const runtime: ViewerRuntime = {
      scene, camera, renderer, controls, loader, modelRoot,
      center: null, requestId: 0,
      currentModel: null, disposed: false, animationFrame: 0, resizeObserver: null,
    }
    runtimeRef.current = runtime

    const resize = () => {
      if (disposed) return
      const { width, height } = host.getBoundingClientRect()
      if (width <= 0 || height <= 0) return
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(host)
    runtime.resizeObserver = resizeObserver
    resize()

    const animate = () => {
      if (disposed) return
      runtime.animationFrame = window.requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const manifestUrl = `${import.meta.env.BASE_URL}anatomy/manifest.json`
    fetch(manifestUrl, { signal: manifestController.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load the anatomy manifest (${response.status}).`)
        return await response.json() as AtlasManifest
      })
      .then((manifest) => {
        if (disposed) return
        const { center, radius } = readManifestBounds(manifest)
        const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.08
        const cameraPosition = new THREE.Vector3(center.x, center.y + 0.04, center.z + distance)
        runtime.center = center
        camera.position.copy(cameraPosition)
        controls.target.copy(center)
        controls.minDistance = Math.max(0.45, radius * 0.72)
        controls.maxDistance = Math.max(8.5, radius * 6)
        controls.update()
        controls.saveState()
        setManifestReady(true)
      })
      .catch((manifestError: unknown) => {
        if (disposed || manifestController.signal.aborted) return
        setError(manifestError instanceof Error ? manifestError.message : 'Could not read the anatomy manifest.')
        setStatus('error')
      })

    return () => {
      disposed = true
      runtime.disposed = true
      runtime.requestId += 1
      manifestController.abort()
      window.cancelAnimationFrame(runtime.animationFrame)
      resizeObserver.disconnect()
      controls.dispose()
      if (runtime.currentModel) disposeModel(runtime.currentModel)
      renderer.dispose()
      renderer.domElement.remove()
      runtimeRef.current = null
    }
  }, [manifestRetryVersion])

  useEffect(() => {
    if (!manifestReady) return
    const runtime = runtimeRef.current
    if (!runtime || runtime.disposed) return

    const requestId = ++runtime.requestId
    if (runtime.currentModel) {
      runtime.modelRoot.remove(runtime.currentModel)
      disposeModel(runtime.currentModel)
      runtime.currentModel = null
    }
    setError(null)
    setProgress(null)
    setStatus('loading-model')

    const modelUrl = `${import.meta.env.BASE_URL}anatomy/${selectedSystem}.glb`
    runtime.loader.load(
      modelUrl,
      (gltf) => {
        if (runtime.disposed || requestId !== runtime.requestId) {
          disposeModel(gltf.scene)
          return
        }

        gltf.scene.name = selectedSystem
        runtime.currentModel = gltf.scene
        runtime.modelRoot.add(gltf.scene)
        setProgress(null)
        setStatus('loaded')
      },
      (event) => {
        if (runtime.disposed || requestId !== runtime.requestId || !event.total) return
        setProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)))
      },
      (loadError) => {
        if (runtime.disposed || requestId !== runtime.requestId) return
        setError(`Unable to load ${selectedSystem}.glb. Check that the anatomy asset is available at ${modelUrl}.`)
        setStatus('error')
        console.error('Anatomy system load failed:', loadError)
      },
    )

    return () => { runtime.requestId += 1 }
  }, [selectedSystem, manifestReady, retryVersion])

  const resetCamera = () => {
    const runtime = runtimeRef.current
    if (!runtime?.center) return
    runtime.controls.reset()
  }

  const retry = () => {
    setError(null)
    if (!manifestReady) {
      setStatus('loading-manifest')
      setManifestRetryVersion((version) => version + 1)
      return
    }
    setStatus('loading-model')
    setRetryVersion((version) => version + 1)
  }

  return <div ref={hostRef} className="anatomy-viewer-host">
    <div className="viewer-live-badge"><span className={`viewer-state-dot ${status === 'loaded' ? 'viewer-state-loaded' : status === 'error' ? 'viewer-state-error' : ''}`} />{status === 'loaded' ? `${selectedSystem.toUpperCase()} · LOADED` : status === 'error' ? 'LOAD ERROR' : status === 'loading-manifest' ? 'READING ATLAS BOUNDS' : `LOADING ${selectedSystem.toUpperCase()}`}</div>
    <button className="viewer-reset-button" onClick={resetCamera} aria-label="Reset camera position"><RotateCcw size={13} /> Reset camera</button>
    {(status === 'loading-manifest' || status === 'loading-model') && <div className="viewer-loading-overlay" role="status"><span className="viewer-spinner" /><strong>{status === 'loading-manifest' ? 'Preparing the anatomy atlas' : `Loading ${selectedSystem} system`}</strong><span>{progress === null ? 'Opening the original compressed model…' : `${progress}% loaded`}</span></div>}
    {status === 'error' && <div className="viewer-error-overlay" role="alert"><div className="viewer-error-icon">!</div><strong>Atlas could not load</strong><p>{error}</p><button onClick={retry}>Retry model</button></div>}
  </div>
}
