import { useState, useEffect } from 'react'
import { Activity, Plus, Trash2, Menu, FileText, Check, Users, ListTodo, Archive, Upload, Briefcase, X, TrendingUp, PieChart, Pencil } from 'lucide-react'
import { apiRequest, jsonOptions } from './api/client'
import { Alert } from './components/common'
import './App.css'


// Always keep project dates in the ISO format required by <input type="date">
// and the FastAPI backend: YYYY-MM-DD.
function getISODate(daysFromToday = 0) {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + daysFromToday)

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')

  return `${year}-${month}-${day}`
}

// Validate and normalize a project date without relying on browser locale formatting.
function normalizeProjectDate(value, fieldName) {
  const raw = String(value ?? '').trim()

  if (!raw) {
    throw new Error(`${fieldName} is required.`)
  }

  let normalized = raw

  // YYYY-MM-DD (preferred format).
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    normalized = raw
  }
  // DD-MM-YYYY.
  else if (/^\d{2}-\d{2}-\d{4}$/.test(raw)) {
    const [day, month, year] = raw.split('-')
    normalized = `${year}-${month}-${day}`
  }
  // DD/MM/YYYY.
  else if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) {
    const [day, month, year] = raw.split('/')
    normalized = `${year}-${month}-${day}`
  }
  else {
    throw new Error(`${fieldName} must be a valid date in YYYY-MM-DD format.`)
  }

  // Check the actual calendar date. JavaScript Date alone can silently roll
  // invalid dates such as 2026-02-31 into March, so compare the components.
  const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) {
    throw new Error(`${fieldName} must be a valid date in YYYY-MM-DD format.`)
  }

  const [, year, month, day] = match
  const parsed = new Date(Number(year), Number(month) - 1, Number(day))

  const valid =
    !Number.isNaN(parsed.getTime()) &&
    parsed.getFullYear() === Number(year) &&
    parsed.getMonth() === Number(month) - 1 &&
    parsed.getDate() === Number(day)

  if (!valid) {
    throw new Error(`${fieldName} must be a valid date.`)
  }

  return normalized
}

const IT_ROLES = [
  "Frontend Developer", "Backend Developer", "Full-Stack Developer", 
  "UI/UX Designer", "QA Engineer", "DevOps Engineer", "Project Manager", 
  "Business Analyst", "Data Scientist", "Security Engineer", "Other"
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [navExpanded, setNavExpanded] = useState(true)
  const [projects, setProjects] = useState([])
  const [employees, setEmployees] = useState([])
  const [archived, setArchived] = useState([])
  const [generatedPlans, setGeneratedPlans] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [currentProject, setCurrentProject] = useState(null)
  const [file, setFile] = useState(null)
  const [generatedPlanResult, setGeneratedPlanResult] = useState(null)
  
  const [editingEmployeeId, setEditingEmployeeId] = useState(null)

  const [projectForm, setProjectForm] = useState({ 
    name: '', project_type: 'Web Application', start_date: getISODate(), deadline: getISODate(30), working_days: [0, 1, 2, 3, 4], holidays: [] 
  })
  
  const [personForm, setPersonForm] = useState({ 
    name: '', role: 'Frontend Developer', customRole: '', additionalRoles: '', hours_per_day: 8, skills: '', leave_dates: '', years_of_experience: 0 
  })

  useEffect(() => { refresh() }, [])

  async function refresh() {
    try {
      const [p, e, a, gp] = await Promise.all([
        apiRequest('/projects'), apiRequest('/employees'),
        // NOTE: '/projects/archive' would be captured by '/projects/{project_id}' and 404.
        apiRequest('/archive').catch(() => []), apiRequest('/plans').catch(() => [])
      ])
      setProjects(p.filter(proj => proj.status !== 'deleted'))
      setEmployees(e); setArchived(a); setGeneratedPlans(gp); setError('')
    } catch (err) { setError(err.message) }
  }

  function navigate(next) {
    setPage(next); setError(''); setNotice(''); 
    if (next === 'wizard') { 
      setCurrentProject(null); setFile(null); setGeneratedPlanResult(null); 
      setProjectForm({ name: '', project_type: 'Web Application', start_date: getISODate(), deadline: getISODate(30), working_days: [0,1,2,3,4], holidays: [] })
    }
    if (next === 'team') {
      resetPersonForm()
    }
  }

  async function handleCreateAndGenerate(e) {
    e.preventDefault()

    // Prevent double submissions while a generation request is running.
    if (busy) return

    setBusy(true)
    setError('')
    setNotice('')

    // A user story PDF is required for plan generation.
    if (!file) {
      setError('Please upload a user story PDF before generating the plan.')
      setBusy(false)
      return
    }

    let finalStartDate
    let finalDeadline

    try {
      finalStartDate = normalizeProjectDate(projectForm.start_date, 'Project start date')
      finalDeadline = normalizeProjectDate(projectForm.deadline, 'Project end date')
    } catch (dateError) {
      setError(dateError.message)
      setBusy(false)
      return
    }

    if (finalStartDate > finalDeadline) {
      setError('Project start date cannot be after the end date.')
      setBusy(false)
      return
    }

    let createdProjectId = null

    try {
      const payload = {
        ...projectForm,
        start_date: finalStartDate,
        deadline: finalDeadline,
        // Ensure the backend receives arrays rather than undefined values.
        working_days: Array.isArray(projectForm.working_days)
          ? projectForm.working_days
          : [0, 1, 2, 3, 4],
        holidays: Array.isArray(projectForm.holidays)
          ? projectForm.holidays
          : []
      }

      // Keep this log while testing so the exact values sent to FastAPI are visible.
      console.log('PROJECT PAYLOAD SENT TO BACKEND:', payload)

      // 1. Create the project with normalized dates.
      const created = await apiRequest('/projects', jsonOptions('POST', payload))
      createdProjectId = created.id

      // 2. Upload the required user-story PDF.
      const formData = new FormData()
      formData.append('file', file)
      await apiRequest(`/projects/${created.id}/upload`, {
        method: 'POST',
        body: formData
      })

      // 3. Generate the plan only after project creation and PDF upload succeed.
      const plan = await apiRequest(`/projects/${created.id}/plan`, {
        method: 'POST'
      })

      // 4. Only show/store the result after successful generation.
      setGeneratedPlanResult(plan)
      setNotice('Plan generated successfully!')
      await refresh()

    } catch (err) {
      console.error('Plan generation failed:', err)
      setError(err.message || 'Failed to generate the plan.')

      // Remove a project that was created only for this failed generation attempt.
      // This prevents failed attempts from accumulating as draft projects.
      if (createdProjectId) {
        try {
          await apiRequest(`/projects/${createdProjectId}`, { method: 'DELETE' })
          await refresh()
        } catch (cleanupErr) {
          console.error('Failed to clean up failed project:', cleanupErr)
        }
      }
    } finally {
      setBusy(false)
    }
  }

  function resetPersonForm() {
    setPersonForm({ name: '', role: 'Frontend Developer', customRole: '', additionalRoles: '', hours_per_day: 8, skills: '', leave_dates: '', years_of_experience: 0 })
    setEditingEmployeeId(null)
  }

  async function savePerson(e) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const finalRole = personForm.role === 'Other' ? personForm.customRole : personForm.role
      const payload = { 
        ...personForm, 
        role: finalRole,
        additional_roles: personForm.additionalRoles.split(',').map(s=>s.trim()).filter(Boolean),
        skills: personForm.skills.split(',').map(s=>s.trim()).filter(Boolean), 
        leave_dates: personForm.leave_dates.split(',').map(s=>s.trim()).filter(Boolean) 
      }
      
      if (editingEmployeeId) {
        await apiRequest(`/employees/${editingEmployeeId}`, jsonOptions('PATCH', payload))
        setNotice('Team member updated successfully.')
      } else {
        await apiRequest('/employees', jsonOptions('POST', payload))
        setNotice('Team member added successfully.')
      }
      
      resetPersonForm()
      await refresh(); 
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  function handleEditClick(emp) {
    setEditingEmployeeId(emp.id)
    setPersonForm({
      name: emp.name || '',
      role: IT_ROLES.includes(emp.role) ? emp.role : 'Other',
      customRole: IT_ROLES.includes(emp.role) ? '' : emp.role,
      additionalRoles: emp.additional_roles ? emp.additional_roles.join(', ') : '',
      hours_per_day: emp.hours_per_day || 8,
      skills: emp.skills ? emp.skills.join(', ') : '',
      leave_dates: emp.leave_dates ? emp.leave_dates.join(', ') : '',
      years_of_experience: emp.years_of_experience || 0
    })
  }

  async function removePerson(id) {
    if(!confirm('Remove this team member?')) return;
    try { await apiRequest(`/employees/${id}`, { method: 'DELETE' }); await refresh() } catch (err) { setError(err.message) }
  }

  async function reviewProjectPlan(projectId) {
    setError('')
    try {
      const plan = await apiRequest(`/projects/${projectId}/plan`)
      setGeneratedPlanResult(plan)
      setPage('wizard')
    } catch (err) {
      setError(err.message)
    }
  }

  async function planAction(planId, action) {
    const confirmText = {
      archive: 'Move this plan to the archive?',
      restore: 'Restore this plan to Generated Plans?',
      delete: 'Permanently delete this plan? This cannot be undone.',
    }[action]
    if (!confirm(confirmText)) return
    setError('')
    try {
      if (action === 'delete') {
        await apiRequest(`/plans/${planId}`, { method: 'DELETE' })
        setNotice('Plan deleted.')
      } else {
        await apiRequest(`/plans/${planId}/${action}`, { method: 'POST' })
        setNotice(action === 'archive' ? 'Plan archived.' : 'Plan restored.')
      }
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function discardProject(id) {
    if(!confirm('Discard this draft project? It will be permanently deleted.')) return;
    try { await apiRequest(`/projects/${id}`, { method: 'DELETE' }); await refresh() } catch (err) { setError(err.message) }
  }

  const totalProj = Math.max(projects.length, 1)
  const generatedCount = projects.filter(p => p.status === 'generated').length
  const draftCount = projects.filter(p => p.status === 'draft').length
  const generatedPct = (generatedCount / totalProj) * 100

  let workloadData = [];
  let maxWorkload = 1;
  if (generatedPlanResult && generatedPlanResult.tasks) {
    const workloadMap = {};
    generatedPlanResult.tasks.forEach(t => {
      if (t.assigned_employee) {
        workloadMap[t.assigned_employee] = (workloadMap[t.assigned_employee] || 0) + (t.estimate_hours || 0);
      }
    });
    workloadData = Object.entries(workloadMap).map(([name, hours]) => ({ name, hours })).sort((a, b) => b.hours - a.hours);
    maxWorkload = Math.max(...workloadData.map(d => d.hours), 1);
  }

  return (
    <div className={`app-shell ${navExpanded ? '' : 'nav-collapsed'}`}>
      <aside className="sidebar" style={{ width: navExpanded ? '250px' : '60px', transition: 'width 0.3s', overflow: 'hidden', background: '#1a3b32', color: 'white' }}>
        <div className="brand-lockup" style={{ padding: '20px 15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity size={24} color="#4ade80" style={{ minWidth: '24px' }} />
          {navExpanded && <strong style={{ fontSize: '1.2rem', color: 'white', whiteSpace: 'nowrap' }}>Autoplan</strong>}
        </div>
        <nav className="side-nav" style={{ display: 'flex', flexDirection: 'column', gap: '5px', padding: '10px' }}>
          <button className={`nav-item ${page === 'dashboard' ? 'active' : ''}`} onClick={() => navigate('dashboard')} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px', background: page === 'dashboard' ? '#2d5247' : 'transparent', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', textAlign: 'left' }}>
            <ListTodo size={20} style={{ minWidth: '20px' }}/> {navExpanded && <span>Dashboard</span>}
          </button>
          <button className={`nav-item ${page === 'wizard' ? 'active' : ''}`} onClick={() => navigate('wizard')} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px', background: page === 'wizard' ? '#2d5247' : 'transparent', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', textAlign: 'left' }}>
            <Plus size={20} style={{ minWidth: '20px' }}/> {navExpanded && <span>New Plan</span>}
          </button>
          <button className={`nav-item ${page === 'team' ? 'active' : ''}`} onClick={() => navigate('team')} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px', background: page === 'team' ? '#2d5247' : 'transparent', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', textAlign: 'left' }}>
            <Users size={20} style={{ minWidth: '20px' }}/> {navExpanded && <span>Team</span>}
          </button>
          <button className={`nav-item ${page === 'plans' ? 'active' : ''}`} onClick={() => navigate('plans')} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px', background: page === 'plans' ? '#2d5247' : 'transparent', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', textAlign: 'left' }}>
            <FileText size={20} style={{ minWidth: '20px' }}/> {navExpanded && <span>Generated Plans</span>}
          </button>
          <button className={`nav-item ${page === 'archive' ? 'active' : ''}`} onClick={() => navigate('archive')} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px', background: page === 'archive' ? '#2d5247' : 'transparent', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', textAlign: 'left' }}>
            <Archive size={20} style={{ minWidth: '20px' }}/> {navExpanded && <span>Archive</span>}
          </button>
        </nav>
      </aside>

      <main className="main-column" style={{ flex: 1, padding: '15px 20px 20px 20px', background: '#f4f7f6', overflowY: 'auto' }}>
        <header className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px', marginBottom: '10px' }}>
          <button onClick={() => setNavExpanded(!navExpanded)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#1a3b32' }}><Menu size={24} /></button>
          <h2 style={{ margin: 0, color: '#1a3b32', fontSize: '1.2rem' }}>Autoplan Generator</h2>
        </header>

        <div className="page-content" style={{ paddingTop: 0 }}>
          {error && <Alert kind="error" message={error} onClose={() => setError('')} />}
          {notice && <Alert kind="success" message={notice} onClose={() => setNotice('')} />}

          {page === 'dashboard' && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                  <h1 style={{ margin: 0, color: '#1a3b32', fontSize: '1.6rem' }}>Dashboard Overview</h1>
                  <p style={{ color: '#64748b', marginTop: '2px', fontSize: '0.9rem' }}>Welcome back to your planning workspace.</p>
                </div>
                <button className="button button-primary" onClick={() => navigate('wizard')} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 20px', background: '#1a3b32', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>
                  <Plus size={18}/> Create New Plan
                </button>
              </div>

              <div style={{ background: '#1a3b32', borderRadius: '24px', padding: '25px', marginBottom: '25px', boxShadow: '0 20px 25px -5px rgba(26, 59, 50, 0.2)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '25px' }}>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div style={{ padding: '20px', background: '#2d5247', borderRadius: '16px', color: 'white', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '5px', color: '#4ade80' }}>
                          <Briefcase size={20} />
                          <span style={{ fontSize: '0.9rem', fontWeight: 600, letterSpacing: '0.5px' }}>ACTIVE PROJECTS</span>
                        </div>
                        <p style={{ fontSize: '2.5rem', margin: 0, fontWeight: 'bold' }}>{projects.length}</p>
                      </div>
                      <div style={{ opacity: 0.1 }}><Briefcase size={32} /></div>
                    </div>

                    <div style={{ padding: '20px', background: '#2d5247', borderRadius: '16px', color: 'white', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '5px', color: '#4ade80' }}>
                          <Users size={20} />
                          <span style={{ fontSize: '0.9rem', fontWeight: 600, letterSpacing: '0.5px' }}>TEAM MEMBERS</span>
                        </div>
                        <p style={{ fontSize: '2.5rem', margin: 0, fontWeight: 'bold' }}>{employees.length}</p>
                      </div>
                      <div style={{ opacity: 0.1 }}><Users size={32} /></div>
                    </div>

                    <div style={{ padding: '20px', background: '#2d5247', borderRadius: '16px', color: 'white', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '5px', color: '#4ade80' }}>
                          <FileText size={20} />
                          <span style={{ fontSize: '0.9rem', fontWeight: 600, letterSpacing: '0.5px' }}>PLANS GENERATED</span>
                        </div>
                        <p style={{ fontSize: '2.5rem', margin: 0, fontWeight: 'bold' }}>{generatedPlans.length}</p>
                      </div>
                      <div style={{ opacity: 0.1 }}><FileText size={32} /></div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div style={{ background: '#2d5247', padding: '20px', borderRadius: '16px', color: 'white', flex: 1, display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
                        <PieChart size={20} color="#4ade80" />
                        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Project Status</h3>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', flex: 1 }}>
                        <div style={{ 
                          width: '100px', height: '100px', borderRadius: '50%', 
                          background: `conic-gradient(#4ade80 ${generatedPct}%, #1a3b32 ${generatedPct}% 100%)`,
                          display: 'flex', justifyContent: 'center', alignItems: 'center'
                        }}>
                          <div style={{ width: '70px', height: '70px', background: '#2d5247', borderRadius: '50%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                            <span style={{ fontSize: '1.2rem', fontWeight: 'bold', color: 'white', lineHeight: 1 }}>{generatedCount}</span>
                          </div>
                        </div>
                        <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#4ade80' }}></div> Generated ({generatedCount})</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#1a3b32' }}></div> Drafts ({draftCount})</div>
                        </div>
                      </div>
                    </div>

                    <div style={{ background: '#2d5247', padding: '20px', borderRadius: '16px', color: 'white' }}>
                       <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
                        <TrendingUp size={20} color="#4ade80" />
                        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Planning Insights</h3>
                      </div>
                      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.9rem' }}>
                        <li style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1a3b32', paddingBottom: '8px' }}>
                          <span style={{ color: '#94a3b8' }}>Avg. Team Experience</span>
                          <strong style={{ color: '#4ade80' }}>{employees.length ? (employees.reduce((acc, e) => acc + (e.years_of_experience || 0), 0) / employees.length).toFixed(1) : 0} Yrs</strong>
                        </li>
                        <li style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1a3b32', paddingBottom: '8px' }}>
                          <span style={{ color: '#94a3b8' }}>Archived Plans</span>
                          <strong style={{ color: '#4ade80' }}>{archived.length}</strong>
                        </li>
                        <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#94a3b8' }}>Draft Projects</span>
                          <strong style={{ color: '#4ade80' }}>{draftCount}</strong>
                        </li>
                      </ul>
                    </div>
                  </div>
                  
                </div>
              </div>

              <h3 style={{ color: '#1a3b32', marginBottom: '15px' }}>Recent Projects</h3>
              <div style={{ display: 'grid', gap: '15px' }}>
                {projects.length === 0 && <p style={{ color: '#64748b' }}>No active projects found. Create a new plan to get started.</p>}
                {projects.map(p => (
                  <div key={p.id} style={{ background: 'white', border: '1px solid #e2e8f0', padding: '20px', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxShadow: '0 1px 3px 0 rgba(0,0,0,0.1)' }}>
                    <div>
                      <h4 style={{ margin: '0 0 5px 0', color: '#1a3b32' }}>{p.name}</h4>
                      <p style={{ margin: 0, color: '#64748b', fontSize: '0.9rem' }}>Deadline: {p.deadline} <span style={{ margin: '0 8px' }}>|</span> Status: <span style={{ color: p.status === 'generated' ? '#16a34a' : '#ea580c', fontWeight: 600 }}>{p.status.toUpperCase()}</span></p>
                    </div>
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                      <button className="button button-outline" onClick={() => reviewProjectPlan(p.id)} disabled={p.status !== 'generated'} style={{ padding: '8px 16px', borderColor: '#1a3b32', color: '#1a3b32', opacity: p.status === 'generated' ? 1 : 0.4 }}>Review Plan</button>
                      <button onClick={() => discardProject(p.id)} title="Discard Draft" style={{ background: 'none', border: '1px solid #ef4444', color: '#ef4444', cursor: 'pointer', borderRadius: '6px', padding: '8px', display: 'flex', alignItems: 'center' }}>
                        <X size={18} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {page === 'wizard' && (
            <div className="wizard-container" style={{ maxWidth: '600px', background: 'white', padding: '30px', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <h2 style={{ marginTop: 0, color: '#1a3b32' }}>Project Details</h2>
              <p style={{ color: '#64748b', marginBottom: '25px' }}>Fill in the details below and upload your requirements to generate a plan.</p>
              
              <form onSubmit={handleCreateAndGenerate} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <span style={{ fontWeight: 500, color: '#334155' }}>Project Name</span>
                  <input required placeholder="e.g. E-commerce App" value={projectForm.name} onChange={e => setProjectForm({...projectForm, name: e.target.value})} style={{ padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                </label>
                
                <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <span style={{ fontWeight: 500, color: '#334155' }}>Project Type</span>
                  <select value={projectForm.project_type} onChange={e => setProjectForm({...projectForm, project_type: e.target.value})} style={{ padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
                    <option>Web Application</option>
                    <option>Mobile Application</option>
                    <option>API Development</option>
                    <option>Cloud Migration</option>
                    <option>AI/ML Project</option>
                    <option>QA Automation</option>
                    <option>Data Engineering</option>
                    <option>Other</option>
                  </select>
                </label>

                {projectForm.project_type === 'Other' && (
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <span style={{ fontWeight: 500, color: '#334155' }}>Custom Project Type</span>
                    <input required placeholder="e.g. IoT Platform" value={projectForm.custom_project_type || ''} onChange={e => setProjectForm({...projectForm, custom_project_type: e.target.value})} style={{ padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                )}

                <div style={{ display: 'flex', gap: '15px' }}>
                  <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <span style={{ fontWeight: 500, color: '#334155' }}>Start Date</span>
                    <input type="date" required value={projectForm.start_date} onChange={e => setProjectForm({...projectForm, start_date: e.target.value})} style={{ padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                  <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <span style={{ fontWeight: 500, color: '#334155' }}>End Date</span>
                    <input type="date" required value={projectForm.deadline} onChange={e => setProjectForm({...projectForm, deadline: e.target.value})} style={{ padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                </div>

                <label style={{ border: '2px dashed #cbd5e1', padding: '30px', textAlign: 'center', cursor: 'pointer', borderRadius: '10px', background: '#f8fafc' }}>
                  <Upload size={32} style={{ color: '#1a3b32', marginBottom: '10px' }} />
                  <div style={{ fontWeight: 500, color: '#334155' }}>{file ? file.name : 'Click to Upload User Story Document (PDF)'}</div>
                  <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '5px' }}>PDF files only</div>
                  <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])} style={{ display: 'none' }} />
                </label>

                <button type="submit" className="button button-primary" disabled={busy} style={{ padding: '14px', fontSize: '1.1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px', background: '#1a3b32', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
                  {busy ? 'Generating Plan...' : <><Check size={20}/> Generate Plan</>}
                </button>
              </form>

              {generatedPlanResult && (
                <div style={{ marginTop: '30px', padding: '20px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
                  <h3 style={{ color: '#1a3b32', display: 'flex', alignItems: 'center', gap: '10px', marginTop: 0 }}><Check /> Plan Generated Successfully</h3>
                  <p><strong>Completion Date:</strong> {generatedPlanResult.completion_date || 'Unknown'}</p>
                  <p><strong>Status:</strong> {generatedPlanResult.deadline_at_risk ? <span style={{color: 'red'}}>At Risk</span> : <span style={{color: 'green'}}>On Track</span>}</p>
                  
                  {workloadData.length > 0 && (
                    <div style={{ marginTop: '20px', marginBottom: '20px' }}>
                      <h4 style={{ color: '#1a3b32', marginBottom: '10px' }}>Team Workload</h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {workloadData.map((w, idx) => (
                          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ width: '120px', fontSize: '0.85rem', color: '#475569', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{w.name}</span>
                            <div style={{ flex: 1, height: '12px', background: '#e2e8f0', borderRadius: '6px', overflow: 'hidden' }}>
                              <div style={{ width: `${(w.hours / maxWorkload) * 100}%`, height: '100%', background: '#1a3b32', borderRadius: '6px' }}></div>
                            </div>
                            <span style={{ fontSize: '0.8rem', color: '#64748b', width: '40px', textAlign: 'right' }}>{w.hours}h</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <h4 style={{ color: '#1a3b32' }}>Assigned Tasks:</h4>
                  <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {generatedPlanResult.tasks.map(t => (
                      <div key={t.id} style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', background: 'white', marginBottom: '5px', borderRadius: '6px' }}>
                        <strong>{t.title}</strong> 
                        <div style={{ fontSize: '0.9rem', color: '#475569', marginTop: '4px' }}>
                          Assigned to <strong>{t.assigned_employee || 'Unassigned'}</strong> ({t.start_date} to {t.end_date})
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {page === 'team' && (
            <div style={{ display: 'flex', gap: '30px', alignItems: 'flex-start' }}>
              <div style={{ flex: 2 }}>
                <h2 style={{ marginTop: 0, color: '#1a3b32' }}>Team Directory</h2>
                {employees.length === 0 && <p style={{ color: '#64748b' }}>No team members yet. Add someone on the right.</p>}
                <div style={{ display: 'grid', gap: '10px' }}>
                  {employees.map(emp => (
                    <div key={emp.id} style={{ padding: '15px', border: '1px solid #e2e8f0', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'white' }}>
                      <div>
                        <h4 style={{ margin: 0, color: '#1a3b32' }}>{emp.name}</h4>
                        <p style={{ margin: '5px 0', color: '#64748b', fontWeight: 500 }}>
                          {emp.role} • {emp.years_of_experience} years exp
                          {emp.additional_roles && emp.additional_roles.length > 0 && <span style={{ color: '#94a3b8', fontWeight: 400 }}> (Also: {emp.additional_roles.join(', ')})</span>}
                        </p>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>Skills: {emp.skills?.join(', ') || 'None listed'}</p>
                      </div>
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button onClick={() => handleEditClick(emp)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3b82f6', padding: '5px' }}><Pencil size={18}/></button>
                        <button onClick={() => removePerson(emp.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '5px' }}><Trash2 size={18}/></button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ flex: 1, maxWidth: '350px', background: 'white', padding: '20px', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px 0 rgba(0,0,0,0.1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <h3 style={{ margin: 0, color: '#1a3b32' }}>{editingEmployeeId ? 'Edit Member' : 'Add Team Member'}</h3>
                  {editingEmployeeId && <button onClick={resetPersonForm} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.85rem' }}>Cancel</button>}
                </div>
                
                <form onSubmit={savePerson} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Name</span>
                    <input required value={personForm.name} onChange={e => setPersonForm({...personForm, name: e.target.value})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                  
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Primary Role</span>
                    <select value={personForm.role} onChange={e => setPersonForm({...personForm, role: e.target.value})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
                      {IT_ROLES.map(r => <option key={r}>{r}</option>)}
                    </select>
                  </label>
                  
                  {personForm.role === 'Other' && (
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Custom Role</span>
                      <input required value={personForm.customRole} onChange={e => setPersonForm({...personForm, customRole: e.target.value})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                    </label>
                  )}

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Additional Roles (comma separated)</span>
                    <input placeholder="QA, Designer" value={personForm.additionalRoles} onChange={e => setPersonForm({...personForm, additionalRoles: e.target.value})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Years of Experience</span>
                    <input type="number" required value={personForm.years_of_experience} onChange={e => setPersonForm({...personForm, years_of_experience: Number(e.target.value)})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                  
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Skills (comma separated)</span>
                    <input placeholder="React, Node.js" value={personForm.skills} onChange={e => setPersonForm({...personForm, skills: e.target.value})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                  
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#334155' }}>Leave Dates (YYYY-MM-DD)</span>
                    <input placeholder="2026-11-01, 2026-11-02" value={personForm.leave_dates} onChange={e => setPersonForm({...personForm, leave_dates: e.target.value})} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '6px' }} />
                  </label>
                  
                  <button className="button button-primary" disabled={busy} style={{ marginTop: '10px', padding: '10px', display: 'flex', justifyContent: 'center', background: '#1a3b32', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
                    {editingEmployeeId ? 'Update Member' : 'Add Member'}
                  </button>
                </form>
              </div>
            </div>
          )}

          {page === 'plans' && (
            <>
              <h2 style={{ marginTop: 0, color: '#1a3b32' }}>Generated Plans</h2>
              {generatedPlans.length === 0 && <p style={{ color: '#64748b' }}>No plans generated yet.</p>}
              <div style={{ display: 'grid', gap: '15px' }}>
                {generatedPlans.map(plan => (
                  <div key={plan.id} style={{ border: '1px solid #e2e8f0', padding: '20px', borderRadius: '10px', background: 'white' }}>
                    <h4 style={{ margin: '0 0 10px 0', color: '#1a3b32' }}>{plan.project_name || `Project ${plan.project_id}`}</h4>
                    <p style={{ color: '#64748b', margin: '0 0 15px 0' }}>
                      Generated on: {new Date(plan.generated_at).toLocaleDateString()}
                      {plan.completion_date && <> <span style={{ margin: '0 8px' }}>|</span> Completes: {plan.completion_date}</>}
                      <span style={{ margin: '0 8px' }}>|</span>
                      {plan.deadline_at_risk ? <span style={{ color: '#dc2626', fontWeight: 600 }}>At Risk</span> : <span style={{ color: '#16a34a', fontWeight: 600 }}>On Track</span>}
                    </p>
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button className="button button-outline" onClick={() => { setGeneratedPlanResult(plan); setPage('wizard'); }} style={{ padding: '8px 16px', borderColor: '#1a3b32', color: '#1a3b32' }}>View Details</button>
                      <button className="button button-outline" onClick={() => planAction(plan.id, 'archive')} style={{ padding: '8px 16px', borderColor: '#64748b', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}><Archive size={16}/> Archive</button>
                      <button onClick={() => planAction(plan.id, 'delete')} style={{ padding: '8px 16px', background: 'none', border: '1px solid #ef4444', color: '#ef4444', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}><Trash2 size={16}/> Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {page === 'archive' && (
            <>
              <h2 style={{ marginTop: 0, color: '#1a3b32' }}>Archived Plans</h2>
              {archived.length === 0 && <p style={{ color: '#64748b' }}>No archived plans.</p>}
              <div style={{ display: 'grid', gap: '15px' }}>
                {archived.map(a => (
                  <div key={a.id} style={{ border: '1px solid #e2e8f0', padding: '20px', marginBottom: '10px', borderRadius: '10px', background: '#f8fafc' }}>
                    <h4 style={{ margin: '0 0 5px 0', color: '#475569' }}>{a.project_name}</h4>
                    <p style={{ color: '#94a3b8', margin: '0 0 12px 0', fontSize: '0.9rem' }}>Archived on: {new Date(a.archived_at).toLocaleDateString()}</p>
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button className="button button-outline" onClick={() => planAction(a.id, 'restore')} style={{ padding: '6px 14px', borderColor: '#1a3b32', color: '#1a3b32' }}>Restore</button>
                      <button onClick={() => planAction(a.id, 'delete')} style={{ padding: '6px 14px', background: 'none', border: '1px solid #ef4444', color: '#ef4444', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}><Trash2 size={14}/> Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}