import React, { useEffect, useState } from "react";
import { Check, ChevronDown, GraduationCap, Loader2 } from "lucide-react";

import { userAPI } from "../services/api";

const CollegeSelector = ({ selectedCollegeId, onCollegeChange, className = "" }) => {
  const [colleges, setColleges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchColleges();
  }, []);

  const fetchColleges = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await userAPI.getColleges();
      setColleges(data.colleges || []);
    } catch (err) {
      console.error("Failed to fetch colleges:", err);
      setError("Failed to load colleges");
    } finally {
      setLoading(false);
    }
  };

  const selectedCollege = colleges.find((c) => c.id === selectedCollegeId);

  if (loading) {
    return (
      <div className={`surface-primary flex items-center gap-2 px-4 py-2.5 ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-[var(--text-muted)]" />
        <span className="type-small text-[var(--text-secondary)]">Loading colleges...</span>
      </div>
    );
  }

  if (error || colleges.length === 0) {
    return (
      <div className={`rounded-[12px] border border-[#d9b4b4] bg-[#f8ecec] px-4 py-2.5 ${className}`}>
        <span className="type-small text-[var(--danger)]">{error || "No colleges available"}</span>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="surface-primary flex w-full items-center justify-between gap-3 px-4 py-3"
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[10px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] text-[var(--accent)]">
            <GraduationCap className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1 text-left">
            <div className="text-sm font-medium text-[var(--text-primary)] truncate">
              {selectedCollege ? selectedCollege.name : "Select a college"}
            </div>
            {selectedCollege?.domain && <div className="text-xs text-[var(--text-muted)] truncate">{selectedCollege.domain}</div>}
          </div>
        </div>
        <ChevronDown className={`h-5 w-5 flex-shrink-0 text-[var(--text-muted)] transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="custom-scrollbar absolute z-50 mt-2 max-h-80 w-full overflow-y-auto rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] shadow-[0_4px_12px_rgba(31,31,28,0.08)]">
            <div className="p-2">
              {colleges.map((college) => (
                <button
                  key={college.id}
                  onClick={() => {
                    onCollegeChange(college.id);
                    setIsOpen(false);
                  }}
                  className={`flex w-full items-center gap-3 rounded-[10px] border px-4 py-3 text-left transition-colors duration-[140ms] ${
                    selectedCollegeId === college.id
                      ? "border-[var(--border-strong)] bg-[var(--bg-subtle)]"
                      : "border-transparent hover:border-[var(--border-soft)] hover:bg-[var(--bg-subtle)]"
                  }`}
                >
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[10px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] text-[var(--accent)]">
                    <GraduationCap className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-[var(--text-primary)]">{college.name}</div>
                    {college.domain && <div className="text-xs text-[var(--text-muted)]">{college.domain}</div>}
                  </div>
                  {selectedCollegeId === college.id && <Check className="h-4 w-4 flex-shrink-0 text-[var(--accent)]" />}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default CollegeSelector;
