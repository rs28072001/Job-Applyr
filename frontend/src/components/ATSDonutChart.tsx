import { useEffect, useState } from "react";

interface ATSDonutChartProps {
  score: number;
  size?: number;
  strokeWidth?: number;
}

export default function ATSDonutChart({ score, size = 160, strokeWidth = 12 }: ATSDonutChartProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;

  useEffect(() => {
    const duration = 1500;
    const steps = 60;
    const increment = score / steps;
    let current = 0;
    
    const timer = setInterval(() => {
      current += increment;
      if (current >= score) {
        setAnimatedScore(score);
        clearInterval(timer);
      } else {
        setAnimatedScore(Math.round(current));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [score]);

  const getColor = (s: number) => {
    if (s >= 80) return "#10b981"; // emerald-500
    if (s >= 60) return "#3b82f6"; // blue-500
    if (s >= 40) return "#f59e0b"; // amber-500
    return "#ef4444"; // red-500
  };

  const color = getColor(animatedScore);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: "stroke-dashoffset 0.3s ease-out",
          }}
        />
      </svg>
      {/* Score in center */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <span className="text-3xl font-bold" style={{ color }}>
            {animatedScore}
          </span>
          <span className="text-sm text-slate-400 block">ATS Score</span>
        </div>
      </div>
    </div>
  );
}
