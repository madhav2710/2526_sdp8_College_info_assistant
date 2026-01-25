import React, { useState, useEffect } from 'react';
import { userAPI } from '../services/api';
import { GraduationCap, ChevronDown, Loader2, Check } from 'lucide-react';

const CollegeSelector = ({ selectedCollegeId, onCollegeChange, className = '' }) => {
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
            console.error('Failed to fetch colleges:', err);
            setError('Failed to load colleges');
        } finally {
            setLoading(false);
        }
    };

    const selectedCollege = colleges.find(c => c.id === selectedCollegeId);

    const handleSelect = (college) => {
        onCollegeChange(college.id);
        setIsOpen(false);
    };

    if (loading) {
        return (
            <div className={`flex items-center gap-2 px-4 py-2 bg-slate-50 rounded-lg border border-slate-200 ${className}`}>
                <Loader2 className="w-4 h-4 animate-spin text-slate-500" />
                <span className="text-sm text-slate-600">Loading colleges...</span>
            </div>
        );
    }

    if (error || colleges.length === 0) {
        return (
            <div className={`px-4 py-2 bg-red-50 rounded-lg border border-red-200 ${className}`}>
                <span className="text-sm text-red-600">{error || 'No colleges available'}</span>
            </div>
        );
    }

    return (
        <div className={`relative ${className}`}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 bg-white border-2 border-slate-300 rounded-xl hover:border-blue-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all shadow-sm"
            >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                        <GraduationCap className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0 text-left">
                        <div className="text-sm font-medium text-slate-900 truncate">
                            {selectedCollege ? selectedCollege.name : 'Select a college'}
                        </div>
                        {selectedCollege?.domain && (
                            <div className="text-xs text-slate-500 truncate">
                                {selectedCollege.domain}
                            </div>
                        )}
                    </div>
                </div>
                <ChevronDown className={`w-5 h-5 text-slate-400 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <>
                    <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute z-50 w-full mt-2 bg-white border-2 border-slate-200 rounded-xl shadow-xl max-h-80 overflow-y-auto custom-scrollbar">
                        <div className="p-2">
                            {colleges.map((college) => (
                                <button
                                    key={college.id}
                                    onClick={() => handleSelect(college)}
                                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all ${
                                        selectedCollegeId === college.id
                                            ? 'bg-blue-50 border-2 border-blue-300'
                                            : 'hover:bg-slate-50 border-2 border-transparent'
                                    }`}
                                >
                                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                                        <GraduationCap className="w-4 h-4 text-white" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium text-slate-900">
                                            {college.name}
                                        </div>
                                        {college.domain && (
                                            <div className="text-xs text-slate-500">
                                                {college.domain}
                                            </div>
                                        )}
                                    </div>
                                    {selectedCollegeId === college.id && (
                                        <Check className="w-5 h-5 text-blue-600 flex-shrink-0" />
                                    )}
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
