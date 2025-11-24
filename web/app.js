/**
 * NC-Edit7 Plot Viewer Application
 * 
 * Integrates:
 * - Tool/Machine selection component
 * - Variable display component  
 * - 3D Plot visualization using three.js
 * - NC Code editor
 */

// Configuration
const CONFIG = {
    cgiUrl: '/ncplot7py/scripts/cgiserver.cgi',
    defaultMachine: 'ISO_MILL',
    colors: {
        rapid: 0xff0000,      // Red for rapid moves (G0)
        linear: 0x00ff00,     // Green for linear moves (G1)
        arc: 0x0000ff,        // Blue for arc moves (G2/G3)
        grid: 0x444444,       // Grid color
        axes: {
            x: 0xff0000,
            y: 0x00ff00,
            z: 0x0000ff
        }
    }
};

// Application state
const state = {
    machines: [],
    currentMachine: null,
    plotData: null,
    variables: {},
    is3DMode: true,
    backgroundColor: 0x1a1a2e
};

// Three.js objects
let scene, camera, renderer, controls;
let toolpathGroup;

/**
 * Initialize the application
 */
async function init() {
    initThreeJS();
    setupEventListeners();
    await loadMachines();
    updateStatus('Ready');
}

/**
 * Initialize Three.js scene
 */
function initThreeJS() {
    const container = document.getElementById('plot-canvas-container');
    const canvas = document.getElementById('plot-canvas');
    
    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(state.backgroundColor);
    
    // Camera
    const aspect = container.clientWidth / container.clientHeight;
    camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 10000);
    camera.position.set(100, 100, 100);
    camera.lookAt(0, 0, 0);
    
    // Renderer
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    
    // Orbit controls for 3D navigation
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enableZoom = true;
    controls.enablePan = true;
    controls.zoomSpeed = 1.2;
    controls.panSpeed = 0.8;
    controls.rotateSpeed = 0.8;
    
    // Grid helper
    const gridHelper = new THREE.GridHelper(200, 20, 0x666666, 0x444444);
    gridHelper.rotation.x = Math.PI / 2; // Rotate to XY plane
    scene.add(gridHelper);
    
    // Axes helper
    const axesHelper = new THREE.AxesHelper(50);
    scene.add(axesHelper);
    
    // Ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    // Directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.4);
    directionalLight.position.set(100, 100, 100);
    scene.add(directionalLight);
    
    // Group for toolpath lines
    toolpathGroup = new THREE.Group();
    scene.add(toolpathGroup);
    
    // Handle window resize
    window.addEventListener('resize', onWindowResize);
    
    // Track mouse position for coordinate display
    renderer.domElement.addEventListener('mousemove', onMouseMove);
    
    // Animation loop
    animate();
}

/**
 * Animation loop
 */
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

/**
 * Handle window resize
 */
function onWindowResize() {
    const container = document.getElementById('plot-canvas-container');
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

/**
 * Track mouse position for coordinate display
 */
function onMouseMove(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    
    // Raycast to get 3D position
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
    
    // Create a plane at Z=0
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const intersection = new THREE.Vector3();
    
    if (raycaster.ray.intersectPlane(plane, intersection)) {
        document.getElementById('status-coords').textContent = 
            `X: ${intersection.x.toFixed(3)} Y: ${intersection.y.toFixed(3)} Z: ${intersection.z.toFixed(3)}`;
    }
}

/**
 * Setup event listeners for UI controls
 */
function setupEventListeners() {
    // Execute button
    document.getElementById('execute-btn').addEventListener('click', executeProgram);
    
    // Background color picker
    document.getElementById('bg-color').addEventListener('input', (e) => {
        const color = e.target.value;
        state.backgroundColor = parseInt(color.replace('#', '0x'), 16);
        scene.background = new THREE.Color(state.backgroundColor);
        document.documentElement.style.setProperty('--bg-color', color);
    });
    
    // Plot controls
    document.getElementById('zoom-in-btn').addEventListener('click', () => {
        camera.position.multiplyScalar(0.8);
    });
    
    document.getElementById('zoom-out-btn').addEventListener('click', () => {
        camera.position.multiplyScalar(1.25);
    });
    
    document.getElementById('reset-view-btn').addEventListener('click', resetView);
    
    document.getElementById('toggle-3d-btn').addEventListener('click', toggle3DMode);
    
    document.getElementById('top-view-btn').addEventListener('click', () => setView('top'));
    document.getElementById('front-view-btn').addEventListener('click', () => setView('front'));
    document.getElementById('side-view-btn').addEventListener('click', () => setView('side'));
}

/**
 * Load available machines from the CGI backend
 */
async function loadMachines() {
    try {
        showLoading(true);
        updateStatus('Loading machines...');
        
        const response = await fetch(CONFIG.cgiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_machines' })
        });
        
        const data = await response.json();
        
        if (data.machines) {
            state.machines = data.machines;
            populateMachineSelect(data.machines);
            addMessage('Loaded ' + data.machines.length + ' machines', 'success');
        } else {
            // Use fallback machines if API is not available
            state.machines = [
                { machineName: 'ISO_MILL', controlType: 'MILL' },
                { machineName: 'FANUC_T', controlType: 'TURN' },
                { machineName: 'SB12RG_F', controlType: 'MILL' },
                { machineName: 'SB12RG_B', controlType: 'MILL' },
                { machineName: 'SR20JII_F', controlType: 'MILL' },
                { machineName: 'SR20JII_B', controlType: 'MILL' }
            ];
            populateMachineSelect(state.machines);
            addMessage('Using default machine list', 'info');
        }
        
        updateStatus('Ready');
    } catch (error) {
        console.error('Error loading machines:', error);
        // Use fallback machines
        state.machines = [
            { machineName: 'ISO_MILL', controlType: 'MILL' },
            { machineName: 'FANUC_T', controlType: 'TURN' },
            { machineName: 'SB12RG_F', controlType: 'MILL' }
        ];
        populateMachineSelect(state.machines);
        addMessage('Could not connect to server, using defaults', 'error');
        updateStatus('Offline mode');
    } finally {
        showLoading(false);
    }
}

/**
 * Populate machine select dropdown
 */
function populateMachineSelect(machines) {
    const select = document.getElementById('machine-select');
    select.innerHTML = '';
    
    machines.forEach(machine => {
        const option = document.createElement('option');
        option.value = machine.machineName;
        option.textContent = `${machine.machineName} (${machine.controlType})`;
        select.appendChild(option);
    });
    
    // Set default
    if (machines.length > 0) {
        state.currentMachine = machines[0].machineName;
    }
}

/**
 * Execute the NC program
 */
async function executeProgram() {
    const program = document.getElementById('nc-code-editor').value;
    const machine = document.getElementById('machine-select').value;
    
    if (!program.trim()) {
        addMessage('Please enter an NC program', 'error');
        return;
    }
    
    try {
        showLoading(true);
        updateStatus('Executing program...');
        addMessage('Sending program to ' + machine, 'info');
        
        const response = await fetch(CONFIG.cgiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                machinedata: [{
                    program: program,
                    machineName: machine,
                    canalNr: 'channel-1'
                }]
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.canal) {
            state.plotData = data.canal;
            
            // Extract and display variables if available
            const canalData = data.canal['channel-1'] || Object.values(data.canal)[0];
            if (canalData) {
                updateVariables(canalData.variables || {});
                renderToolpath(canalData.segments || []);
            }
            
            // Show messages
            if (data.message) {
                data.message.forEach(msg => addMessage(msg, 'success'));
            }
            
            addMessage('Program executed successfully', 'success');
            updateStatus('Execution complete');
        } else {
            addMessage('Execution failed: ' + (data.error || 'Unknown error'), 'error');
            if (data.message_TEST) {
                data.message_TEST.forEach(msg => addMessage(msg, 'error'));
            }
            updateStatus('Execution failed');
        }
    } catch (error) {
        console.error('Error executing program:', error);
        addMessage('Error: ' + error.message, 'error');
        updateStatus('Error');
        
        // Demo mode - generate sample toolpath
        generateDemoToolpath();
    } finally {
        showLoading(false);
    }
}

/**
 * Generate demo toolpath when server is unavailable
 */
function generateDemoToolpath() {
    const program = document.getElementById('nc-code-editor').value;
    const lines = program.split('\n');
    const segments = [];
    let currentPos = { x: 0, y: 0, z: 0 };
    
    lines.forEach((line, index) => {
        const trimmed = line.trim().toUpperCase();
        if (trimmed.startsWith('G0') || trimmed.startsWith('G1')) {
            const newPos = { ...currentPos };
            
            // Parse X, Y, Z values
            const xMatch = trimmed.match(/X(-?\d+\.?\d*)/);
            const yMatch = trimmed.match(/Y(-?\d+\.?\d*)/);
            const zMatch = trimmed.match(/Z(-?\d+\.?\d*)/);
            
            if (xMatch) newPos.x = parseFloat(xMatch[1]);
            if (yMatch) newPos.y = parseFloat(yMatch[1]);
            if (zMatch) newPos.z = parseFloat(zMatch[1]);
            
            segments.push({
                type: trimmed.startsWith('G0') ? 'RAPID' : 'LINEAR',
                lineNumber: index + 1,
                toolNumber: 1,
                points: [
                    { x: currentPos.x, y: currentPos.y, z: currentPos.z },
                    { x: newPos.x, y: newPos.y, z: newPos.z }
                ]
            });
            
            currentPos = newPos;
        }
    });
    
    renderToolpath(segments);
    addMessage('Demo mode: Local parsing used', 'info');
}

/**
 * Update variables display
 */
function updateVariables(variables) {
    state.variables = variables;
    const container = document.getElementById('variable-list');
    container.innerHTML = '';
    
    const keys = Object.keys(variables);
    
    if (keys.length === 0) {
        container.innerHTML = '<div class="variable-item"><span class="variable-name">No variables</span><span class="variable-value">-</span></div>';
        return;
    }
    
    keys.forEach(key => {
        const item = document.createElement('div');
        item.className = 'variable-item';
        item.innerHTML = `
            <span class="variable-name">${key}</span>
            <span class="variable-value">${variables[key]}</span>
        `;
        container.appendChild(item);
    });
}

/**
 * Clear toolpath and dispose of Three.js resources to prevent memory leaks
 */
function clearToolpath() {
    while (toolpathGroup.children.length > 0) {
        const child = toolpathGroup.children[0];
        
        // Dispose geometry
        if (child.geometry) {
            child.geometry.dispose();
        }
        
        // Dispose material(s)
        if (child.material) {
            if (Array.isArray(child.material)) {
                child.material.forEach(mat => mat.dispose());
            } else {
                child.material.dispose();
            }
        }
        
        toolpathGroup.remove(child);
    }
}

/**
 * Render toolpath in 3D view
 */
function renderToolpath(segments) {
    // Clear existing toolpath and dispose resources to prevent memory leaks
    clearToolpath();
    
    if (!segments || segments.length === 0) {
        addMessage('No toolpath segments to display', 'info');
        return;
    }
    
    let bounds = {
        minX: Infinity, maxX: -Infinity,
        minY: Infinity, maxY: -Infinity,
        minZ: Infinity, maxZ: -Infinity
    };
    
    segments.forEach(segment => {
        if (!segment.points || segment.points.length < 2) return;
        
        // Determine color based on segment type
        let color;
        switch (segment.type) {
            case 'RAPID':
                color = CONFIG.colors.rapid;
                break;
            case 'LINEAR':
                color = CONFIG.colors.linear;
                break;
            case 'ARC_CW':
            case 'ARC_CCW':
                color = CONFIG.colors.arc;
                break;
            default:
                color = CONFIG.colors.linear;
        }
        
        const material = new THREE.LineBasicMaterial({ 
            color: color,
            linewidth: segment.type === 'RAPID' ? 1 : 2
        });
        
        const geometry = new THREE.BufferGeometry();
        const points = [];
        
        segment.points.forEach(point => {
            const x = point.x || 0;
            const y = point.y || 0;
            const z = point.z || 0;
            
            points.push(x, y, z);
            
            // Update bounds
            bounds.minX = Math.min(bounds.minX, x);
            bounds.maxX = Math.max(bounds.maxX, x);
            bounds.minY = Math.min(bounds.minY, y);
            bounds.maxY = Math.max(bounds.maxY, y);
            bounds.minZ = Math.min(bounds.minZ, z);
            bounds.maxZ = Math.max(bounds.maxZ, z);
        });
        
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
        
        const line = new THREE.Line(geometry, material);
        toolpathGroup.add(line);
        
        // Add a small sphere at start point for visibility
        if (segment === segments[0]) {
            const sphereGeometry = new THREE.SphereGeometry(1, 8, 8);
            const sphereMaterial = new THREE.MeshBasicMaterial({ color: 0xffff00 });
            const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
            sphere.position.set(segment.points[0].x || 0, segment.points[0].y || 0, segment.points[0].z || 0);
            toolpathGroup.add(sphere);
        }
    });
    
    // Fit view to bounds
    fitViewToBounds(bounds);
    
    addMessage(`Rendered ${segments.length} segments`, 'info');
}

/**
 * Fit camera view to toolpath bounds
 */
function fitViewToBounds(bounds) {
    if (bounds.minX === Infinity) return;
    
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;
    const centerZ = (bounds.minZ + bounds.maxZ) / 2;
    
    const sizeX = bounds.maxX - bounds.minX;
    const sizeY = bounds.maxY - bounds.minY;
    const sizeZ = bounds.maxZ - bounds.minZ;
    
    const maxSize = Math.max(sizeX, sizeY, sizeZ, 10);
    const distance = maxSize * 2;
    
    controls.target.set(centerX, centerY, centerZ);
    
    if (state.is3DMode) {
        camera.position.set(
            centerX + distance * 0.7,
            centerY + distance * 0.7,
            centerZ + distance * 0.7
        );
    } else {
        camera.position.set(centerX, centerY, distance);
    }
    
    camera.lookAt(centerX, centerY, centerZ);
    controls.update();
}

/**
 * Reset view to default position
 */
function resetView() {
    camera.position.set(100, 100, 100);
    controls.target.set(0, 0, 0);
    camera.lookAt(0, 0, 0);
    controls.update();
    addMessage('View reset', 'info');
}

/**
 * Toggle between 3D and 2D mode
 */
function toggle3DMode() {
    state.is3DMode = !state.is3DMode;
    const btn = document.getElementById('toggle-3d-btn');
    
    if (state.is3DMode) {
        btn.textContent = '3D Mode';
        controls.enableRotate = true;
        camera.position.set(100, 100, 100);
    } else {
        btn.textContent = '2D Mode';
        controls.enableRotate = false;
        setView('top');
    }
    
    controls.update();
    addMessage(state.is3DMode ? '3D mode enabled' : '2D mode enabled', 'info');
}

/**
 * Set camera to specific view angle
 */
function setView(view) {
    const distance = 200;
    const target = controls.target;
    
    switch (view) {
        case 'top': // XY plane (looking down Z)
            camera.position.set(target.x, target.y, target.z + distance);
            camera.up.set(0, 1, 0);
            break;
        case 'front': // XZ plane (looking along Y)
            camera.position.set(target.x, target.y - distance, target.z);
            camera.up.set(0, 0, 1);
            break;
        case 'side': // YZ plane (looking along X)
            camera.position.set(target.x + distance, target.y, target.z);
            camera.up.set(0, 0, 1);
            break;
    }
    
    camera.lookAt(target);
    controls.update();
    addMessage(`View: ${view}`, 'info');
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.toggle('active', show);
}

/**
 * Update status bar message
 */
function updateStatus(message) {
    document.getElementById('status-message').textContent = message;
}

/**
 * Add message to messages panel
 */
function addMessage(text, type = 'info') {
    const list = document.getElementById('message-list');
    const item = document.createElement('div');
    item.className = `message-item ${type}`;
    item.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    list.insertBefore(item, list.firstChild);
    
    // Keep only last 50 messages
    while (list.children.length > 50) {
        list.removeChild(list.lastChild);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
