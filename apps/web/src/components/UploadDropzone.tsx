"use client";

import { useRef, useState } from "react";

type UploadDropzoneProps = {
  onFileSelected?: (file: File) => void;
};

export function UploadDropzone({ onFileSelected }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [filename, setFilename] = useState("No file selected");

  return (
    <div className="dropzone">
      <input
        ref={inputRef}
        hidden
        type="file"
        accept=".pdf,.xlsx,.xlsm"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          setFilename(file.name);
          onFileSelected?.(file);
        }}
      />
      <div>
        <div className="eyebrow">Step 1</div>
        <h2>Upload your statement</h2>
        <p>PDF, XLSX, or XLSM. Your preview will show a limited report first.</p>
        <p>
          <strong>{filename}</strong>
        </p>
        <button className="button" type="button" onClick={() => inputRef.current?.click()}>
          Choose file
        </button>
      </div>
    </div>
  );
}
