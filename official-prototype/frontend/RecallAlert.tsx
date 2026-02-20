/**
 * Compact recall details block: date, reason, hazard level, manufacturer, distribution, action text.
 */
import { AlertTriangle, Calendar, FileText } from 'lucide-react';
import type { RecallInfo } from './types';

interface RecallAlertProps {
  recall: RecallInfo;
}

export const RecallAlert = ({ recall }: RecallAlertProps) => {
  return (
    <div className="rounded-xl border border-black/5 bg-black/[0.02] p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-[#1A1A1A] shrink-0 mt-0.5" />
        <div className="flex-1 space-y-3 min-w-0">
          <h4 className="font-semibold text-[#1A1A1A]">Recall information</h4>
          <div className="space-y-2 text-sm text-[#888]">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#888]" />
              <span className="font-medium text-[#1A1A1A]">Date:</span>
              <span>{new Date(recall.recall_date).toLocaleDateString()}</span>
            </div>
            <div className="flex items-start gap-2">
              <FileText className="w-4 h-4 text-[#888] shrink-0 mt-0.5" />
              <div>
                <span className="font-medium text-[#1A1A1A]">Reason:</span>
                <p className="mt-1">{recall.reason}</p>
              </div>
            </div>
            <div>
              <span className="font-medium text-[#1A1A1A]">Hazard level:</span> {recall.hazard_classification}
            </div>
            {recall.firm_name && (
              <div>
                <span className="font-medium text-[#1A1A1A]">Manufacturer:</span> {recall.firm_name}
              </div>
            )}
            {recall.distribution && (
              <div>
                <span className="font-medium text-[#1A1A1A]">Distribution:</span> {recall.distribution}
              </div>
            )}
          </div>
          <div className="pt-3 border-t border-black/10">
            <p className="font-medium text-[#1A1A1A] text-sm">
              Action required: {recall.hazard_classification === 'Class I'
                ? 'Discard immediately or return to store.'
                : 'Check lot code and return if affected.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
