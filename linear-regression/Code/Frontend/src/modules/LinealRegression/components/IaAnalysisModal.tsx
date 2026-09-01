import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface IaModalProps {
  open: boolean;
  onClose: () => void;
  content: string | null;
}

export const IaAnalysisModal = ({ open, onClose, content }: IaModalProps) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center">
      {/* overlay */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* modal */}
      <div className="relative z-10 w-full max-w-4xl max-h-[85vh] bg-white rounded-xl shadow-lg flex flex-col">
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            Explicación de los resultados de la regresión
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-800 text-xl"
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>

        {/* body */}
        <div
          className="
    px-4 sm:px-6 py-6
    overflow-y-auto
    prose max-w-full
  "
        >
          {content === null ? (
            <div className="flex flex-col items-center gap-3 text-gray-500 w-full">
              <div className="relative h-1 w-48 overflow-hidden rounded bg-gray-200">
                <div className="absolute inset-y-0 w-1/3 bg-gray-500 animate-loading-bar" />
              </div>
              <span className="text-sm">Generando explicación…</span>
            </div>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table({ children }) {
                  return (
                    <div className="overflow-x-auto w-full">
                      <table className="w-full">{children}</table>
                    </div>
                  );
                },
                pre({ children }) {
                  return <pre className="overflow-x-auto">{children}</pre>;
                },
                code({ children }) {
                  return <code className="break-words">{children}</code>;
                },
              }}
            >
              {content}
            </ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  );
};
