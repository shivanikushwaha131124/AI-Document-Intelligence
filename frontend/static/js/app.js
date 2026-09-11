const API_BASE = "";


// =========================================================
// COMMON HELPERS
// =========================================================

function escapeHTML(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatDocumentType(type) {

    const names = {

        invoice: "Invoice",

        balance_sheet:
            "Balance Sheet",

        profit_and_loss:
            "Profit & Loss",

        cash_flow_statement:
            "Cash Flow Statement"
    };

    return names[type] || type || "-";
}


function statusHTML(status) {

    if (status === "PASS") {

        return `
            <span class="status status-pass">
                PASS
            </span>
        `;
    }

    if (status === "NOT_APPLICABLE") {

        return `
            <span class="status status-na">
                NOT APPLICABLE
            </span>
        `;
    }

    return `
        <span class="status status-failed">
            ${escapeHTML(status || "FAILED")}
        </span>
    `;
}


function valueHTML(value) {

    if (value === null || value === undefined || value === "") {

        return `
            <span class="status status-na">
                Missing / Unreadable
            </span>
        `;
    }

    if (typeof value === "object") {

        return `
            <pre>${escapeHTML(
                JSON.stringify(value, null, 2)
            )}</pre>
        `;
    }

    return escapeHTML(value);
}


// =========================================================
// DASHBOARD
// =========================================================

const uploadForm =
    document.getElementById("uploadForm");


if (uploadForm) {

    const documentType =
        document.getElementById("documentType");

    const documentFile =
        document.getElementById("documentFile");

    const processButton =
        document.getElementById("processButton");

    const uploadMessage =
        document.getElementById("uploadMessage");

    const tableBody =
        document.getElementById("documentsTableBody");

    const refreshButton =
        document.getElementById("refreshButton");

    const healthStatus =
        document.getElementById("healthStatus");


    function showMessage(message, type) {

        uploadMessage.textContent =
            message;

        uploadMessage.className =
            `message ${type}`;
    }


    function hideMessage() {

        uploadMessage.className =
            "message hidden";
    }


    async function checkHealth() {

        try {

            const response =
                await fetch(
                    `${API_BASE}/api/v1/health`
                );

            if (!response.ok) {
                throw new Error();
            }

            const data =
                await response.json();

            healthStatus.textContent =
                `● ${data.status}`;

        } catch {

            healthStatus.textContent =
                "● API Offline";
        }
    }


    async function loadDocuments() {

        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    Loading documents...
                </td>
            </tr>
        `;

        try {

            const response =
                await fetch(
                    `${API_BASE}/api/v1/documents`
                );

            if (!response.ok) {
                throw new Error();
            }

            const documents =
                await response.json();

            if (!documents.length) {

                tableBody.innerHTML = `
                    <tr>
                        <td colspan="5">
                            No documents processed yet.
                        </td>
                    </tr>
                `;

                return;
            }

            tableBody.innerHTML =
                documents.map(document => {

                    const encodedName =
                        encodeURIComponent(
                            document.document_name
                        );

                    const processedAt =
                        document.processed_at
                            ? new Date(
                                document.processed_at
                            ).toLocaleString()
                            : "-";

                    return `
                        <tr>

                            <td>
                                ${escapeHTML(
                                    document.document_name
                                )}
                            </td>

                            <td>
                                ${formatDocumentType(
                                    document.document_type
                                )}
                            </td>

                            <td>
                                ${statusHTML(
                                    document.processing_status
                                )}
                            </td>

                            <td>
                                ${escapeHTML(
                                    processedAt
                                )}
                            </td>

                            <td>
                                <button
                                    class="open-button"
                                    onclick="openDocument('${encodedName}')"
                                >
                                    Open
                                </button>
                            </td>

                        </tr>
                    `;

                }).join("");

        } catch {

            tableBody.innerHTML = `
                <tr>
                    <td colspan="5">
                        Unable to load documents.
                        Make sure the backend is running.
                    </td>
                </tr>
            `;
        }
    }


    window.openDocument =
        function(encodedName) {

            window.location.href =
                `/document_result.html?name=${encodedName}`;
        };


    uploadForm.addEventListener(
        "submit",
        async function(event) {

            event.preventDefault();

            hideMessage();

            const type =
                documentType.value;

            const file =
                documentFile.files[0];

            if (!type) {

                showMessage(
                    "Please select a document type.",
                    "error"
                );

                return;
            }

            if (!file) {

                showMessage(
                    "Please select a document.",
                    "error"
                );

                return;
            }

            const allowedExtensions =
                [
                    ".pdf",
                    ".jpg",
                    ".jpeg",
                    ".png"
                ];

            const filename =
                file.name.toLowerCase();

            const supported =
                allowedExtensions.some(
                    extension =>
                        filename.endsWith(extension)
                );

            if (!supported) {

                showMessage(
                    "Only PDF, JPG, JPEG and PNG files are supported.",
                    "error"
                );

                return;
            }


            const formData =
                new FormData();

            formData.append(
                "file",
                file
            );

            formData.append(
                "document_type",
                type
            );


            processButton.disabled =
                true;

            processButton.textContent =
                "Processing...";


            try {

                const response =
                    await fetch(
                        `${API_BASE}/api/v1/documents/process`,
                        {
                            method: "POST",
                            body: formData
                        }
                    );

                const data =
                    await response.json();


                if (!response.ok) {

                    const message =
                        data?.detail?.message ||
                        "Document processing failed.";

                    throw new Error(message);
                }


                showMessage(
                    "Document processed successfully!",
                    "success"
                );

                uploadForm.reset();

                await loadDocuments();


                const encodedName =
                    encodeURIComponent(
                        data.document_name
                    );


                setTimeout(
                    function() {

                        window.location.href =
                            `/document_result.html?name=${encodedName}`;

                    },
                    600
                );


            } catch (error) {

                showMessage(
                    error.message ||
                    "Something went wrong.",
                    "error"
                );

            } finally {

                processButton.disabled =
                    false;

                processButton.textContent =
                    "Process Document";
            }

        }
    );


    refreshButton.addEventListener(
        "click",
        loadDocuments
    );


    checkHealth();

    loadDocuments();
}


// =========================================================
// RESULT PAGE
// =========================================================

const resultName =
    document.getElementById("resultName");


if (resultName) {

    loadDocumentResult();
}


async function loadDocumentResult() {

    const params =
        new URLSearchParams(
            window.location.search
        );

    const documentName =
        params.get("name");


    if (!documentName) {

        document.getElementById(
            "documentTitle"
        ).textContent =
            "No document specified.";

        return;
    }


    try {

        const response =
            await fetch(
                `${API_BASE}/api/v1/documents/${documentName}`
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data?.detail?.message ||
                "Document not found."
            );
        }


        renderResult(data);


    } catch (error) {

        document.getElementById(
            "documentTitle"
        ).textContent =
            error.message;

    }
}


// =========================================================
// RESULT RENDERING
// =========================================================

function renderResult(data) {

    document.getElementById(
        "documentTitle"
    ).textContent =
        formatDocumentType(
            data.document_type
        );


    document.getElementById(
        "resultName"
    ).textContent =
        data.document_name || "-";


    document.getElementById(
        "resultType"
    ).textContent =
        formatDocumentType(
            data.document_type
        );


    document.getElementById(
        "resultStatus"
    ).innerHTML =
        statusHTML(
            data.processing_status
        );


    const fileValidation =
        data.file_validation || {};


    document.getElementById(
        "resultFileType"
    ).textContent =
        fileValidation.file_type || "-";


    document.getElementById(
        "resultPages"
    ).textContent =
        fileValidation.page_count ?? "-";


    const metadata =
        data.processing_metadata || {};


    document.getElementById(
        "resultOCR"
    ).textContent =
        metadata.ocr_used
            ? "Yes"
            : "No";


    renderValidation(
        data.validation || {}
    );


    renderFields(
        data.extracted_data || {}
    );


    renderTables(
        data.extracted_data || {}
    );


    document.getElementById(
        "metadataContainer"
    ).textContent =
        JSON.stringify(
            metadata,
            null,
            2
        );


    document.getElementById(
        "rawJSON"
    ).textContent =
        JSON.stringify(
            data,
            null,
            2
        );
}


// =========================================================
// VALIDATION
// =========================================================

function renderValidation(validation) {

    const container =
        document.getElementById(
            "validationContainer"
        );


    const overall =
        validation.overall_status ||
        "NOT_APPLICABLE";


    document.getElementById(
        "overallValidation"
    ).innerHTML =
        statusHTML(overall);


    const checks =
        validation.checks || [];


    if (!checks.length) {

        container.innerHTML = `
            <div class="empty-state">
                No validation checks available.
            </div>
        `;

        return;
    }


    container.innerHTML =
        checks.map(check => {

            const status =
                check.status ||
                "NOT_APPLICABLE";


            const cssClass =
                status === "PASS"
                    ? "pass"
                    : status === "FAIL"
                        ? "fail"
                        : "na";


            return `
                <div class="validation-card ${cssClass}">

                    <div class="validation-header">

                        <strong>
                            ${escapeHTML(
                                check.name || "Validation Check"
                            )}
                        </strong>

                        ${statusHTML(status)}

                    </div>


                    <div class="validation-formula">

                        ${escapeHTML(
                            check.formula || "-"
                        )}

                    </div>


                    <div class="operands">

                        <strong>Operands:</strong>

                        <pre>${escapeHTML(
                            JSON.stringify(
                                check.operands || {},
                                null,
                                2
                            )
                        )}</pre>

                    </div>


                    <div>
                        <strong>Calculated:</strong>
                        ${check.calculated_value ?? "-"}
                    </div>

                    <div>
                        <strong>Reported:</strong>
                        ${check.reported_value ?? "-"}
                    </div>

                    <div>
                        <strong>Variance:</strong>
                        ${check.variance ?? "-"}
                    </div>


                    ${
                        check.reason
                            ? `
                                <div class="issue">
                                    ${escapeHTML(
                                        check.reason
                                    )}
                                </div>
                            `
                            : ""
                    }

                </div>
            `;

        }).join("");
}


// =========================================================
// FIELDS
// =========================================================

function renderFields(extractedData) {

    const container =
        document.getElementById(
            "fieldsContainer"
        );


    const fields =
        extractedData.fields || {};


    const entries =
        Object.entries(fields);


    if (!entries.length) {

        container.innerHTML = `
            <div class="empty-state">
                No structured fields extracted.
            </div>
        `;

        return;
    }


    container.innerHTML = `
        <div class="field-grid">

            ${
                entries.map(
                    ([name, field]) => {

                        const value =
                            field?.value;


                        const evidence =
                            field?.evidence ||
                            {};


                        const missing =
                            value === null ||
                            value === undefined ||
                            value === "";


                        return `
                            <div class="field-card ${
                                missing
                                    ? "missing"
                                    : ""
                            }">

                                <div class="field-name">
                                    ${escapeHTML(
                                        name
                                    )}
                                </div>

                                <div class="field-value">

                                    ${
                                        valueHTML(
                                            value
                                        )
                                    }

                                </div>


                                ${
                                    evidence.source_text ||
                                    evidence.page_number
                                        ? `
                                            <div class="evidence">

                                                <strong>
                                                    Evidence
                                                </strong>

                                                ${
                                                    evidence.page_number
                                                        ? `<div>
                                                            Page:
                                                            ${evidence.page_number}
                                                        </div>`
                                                        : ""
                                                }

                                                ${
                                                    evidence.source_text
                                                        ? `<div>
                                                            Source:
                                                            ${escapeHTML(
                                                                evidence.source_text
                                                            )}
                                                        </div>`
                                                        : ""
                                                }

                                            </div>
                                        `
                                        : ""
                                }

                            </div>
                        `;
                    }
                ).join("")
            }

        </div>
    `;
}


// =========================================================
// TABLES
// =========================================================

function renderTables(extractedData) {

    const container =
        document.getElementById(
            "tablesContainer"
        );


    const tables =
        extractedData.tables || [];


    if (!tables.length) {

        container.innerHTML = `
            <div class="empty-state">
                No tables extracted.
            </div>
        `;

        return;
    }


    container.innerHTML =
        tables.map(table => {

            const rows =
                table.rows || [];


            if (!rows.length) {

                return `
                    <div class="empty-state">
                        ${escapeHTML(
                            table.table_name ||
                            "Table"
                        )}

                        — No rows extracted.
                    </div>
                `;
            }


            return `
                <div class="table-wrapper">

                    <h3>
                        ${escapeHTML(
                            table.table_name ||
                            "Extracted Table"
                        )}
                    </h3>


                    <table class="table-data">

                        <thead>

                            <tr>
                                <th>Label</th>
                                <th>Values</th>
                                <th>Evidence</th>
                            </tr>

                        </thead>


                        <tbody>

                            ${
                                rows.map(row => {

                                    return `
                                        <tr>

                                            <td>
                                                ${escapeHTML(
                                                    row.label ||
                                                    row.raw_text ||
                                                    "-"
                                                )}
                                            </td>

                                            <td>

                                                ${
                                                    valueHTML(
                                                        row.values
                                                    )
                                                }

                                            </td>

                                            <td>

                                                ${
                                                    row.evidence?.page_number
                                                        ? `Page ${row.evidence.page_number}`
                                                        : "-"
                                                }

                                                ${
                                                    row.evidence?.source_text
                                                        ? `<br>
                                                           ${escapeHTML(
                                                               row.evidence.source_text
                                                           )}`
                                                        : ""
                                                }

                                            </td>

                                        </tr>
                                    `;

                                }).join("")
                            }

                        </tbody>

                    </table>

                </div>
            `;

        }).join("");
}


// =========================================================
// NAVIGATION
// =========================================================

function goToDashboard() {

    window.location.href =
        "/dashboard.html";
}


// =========================================================
// COPY JSON
// =========================================================

async function copyRawJSON() {

    const raw =
        document.getElementById(
            "rawJSON"
        ).textContent;


    try {

        await navigator.clipboard.writeText(
            raw
        );

        alert(
            "JSON copied successfully."
        );

    } catch {

        alert(
            "Unable to copy JSON."
        );
    }
}