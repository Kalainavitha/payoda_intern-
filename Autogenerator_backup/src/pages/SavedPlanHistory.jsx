import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

export default function SavedPlanHistory() {
  const { projectId } = useParams();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPlan = async () => {
      try {
        const response = await axios.get(`http://127.0.0.1:8001/api/projects/${projectId}/plan`);
        setPlan(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load plan");
      } finally {
        setLoading(false);
      }
    };
    fetchPlan();
  }, [projectId]);

  if (loading) return <div className="p-8 text-center">Loading schedule...</div>;
  if (error) return <div className="p-8 text-red-500 text-center">{error}</div>;
  if (!plan) return <div className="p-8 text-center">No plan generated yet.</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Generated Plan</h1>
      
      {/* Plan Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-4 rounded shadow border">
          <div className="text-gray-500 text-sm">Total Tasks</div>
          <div className="text-2xl font-bold">{plan.scheduled_tasks} / {plan.total_tasks}</div>
        </div>
        <div className="bg-white p-4 rounded shadow border">
          <div className="text-gray-500 text-sm">Estimated Completion</div>
          <div className="text-2xl font-bold">{plan.completion_date || 'Pending'}</div>
        </div>
        <div className="bg-white p-4 rounded shadow border">
          <div className="text-gray-500 text-sm">Deadline</div>
          <div className="text-2xl font-bold">{plan.deadline}</div>
        </div>
        <div className={`p-4 rounded shadow border ${plan.deadline_at_risk ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
          <div className="text-gray-500 text-sm">Status</div>
          <div className={`text-2xl font-bold ${plan.deadline_at_risk ? 'text-red-600' : 'text-green-600'}`}>
            {plan.deadline_at_risk ? 'At Risk' : 'On Track'}
          </div>
        </div>
      </div>

      {/* Warnings */}
      {plan.warnings && plan.warnings.length > 0 && (
        <div className="mb-8 bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <h3 className="font-bold text-yellow-800">Scheduling Warnings</h3>
          <ul className="list-disc ml-5 mt-2 text-yellow-700">
            {plan.warnings.map((w, idx) => (
              <li key={idx}>{w.message}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Task List */}
      <div className="bg-white rounded shadow border overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Task</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Assigned To</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Dates</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Hours</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {plan.tasks.map((task) => (
              <tr key={task.id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="font-medium text-gray-900">{task.title}</div>
                  <div className="text-sm text-gray-500">{task.phase}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {task.assigned_employee || 'Unassigned'}
                  {task.assigned_employee_experience > 0 && (
                    <span className="text-gray-500 text-xs ml-1">({task.assigned_employee_experience}y exp)</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {task.start_date} to {task.end_date}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {task.remaining_hours} / {task.estimate_hours}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className={`px-2 py-1 rounded text-xs font-bold 
                    ${task.priority === 'Critical' ? 'bg-red-100 text-red-800' : 
                      task.priority === 'High' ? 'bg-orange-100 text-orange-800' : 
                      task.priority === 'Medium' ? 'bg-blue-100 text-blue-800' : 
                      'bg-gray-100 text-gray-800'}`}>
                    {task.priority}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}