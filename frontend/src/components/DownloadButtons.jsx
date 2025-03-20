import React from 'react';
import { FileText, FileSpreadsheet } from 'lucide-react';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';

const DownloadButtons = ({ data }) => {
    const exportToCSV = () => {
        const csvData = data.map(row => Object.values(row).join(',')).join('\n');
        const blob = new Blob([csvData], { type: 'text/csv' });
        saveAs(blob, 'query_results.csv');
    };

    const exportToExcel = () => {
        const worksheet = XLSX.utils.json_to_sheet(data);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Results');
        XLSX.writeFile(workbook, 'query_results.xlsx');
    };

    return (
        <div className="d-flex gap-2 mt-3">
            <button className="btn btn-outline-secondary" onClick={exportToCSV}>
                <FileText size={16} /> Download CSV
            </button>
            <button className="btn btn-outline-success" onClick={exportToExcel}>
                <FileSpreadsheet size={16} /> Download Excel
            </button>
        </div>
    );
};

export default DownloadButtons;
