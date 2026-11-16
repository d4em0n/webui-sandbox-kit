<script>
  import { onMount } from "svelte";
  import { getSessionUser } from "$lib/apis/auths";
  import FilePreview from "$lib/components/chat/FileNav/FilePreview.svelte";
  import DOMPurify from "dompurify";
  import { readExcelWorkbook, excelToTable } from "$lib/utils/excelToTable";

  let name = "",
    error = "",
    loading = true,
    pdf = null,
    docx = null,
    slides = null;
  let workbook = null,
    sheets = [],
    selectedSheet = "",
    html = null;
  let originalUrl = "",
    token = "",
    targetPage = null;
  const abort = new AbortController();

  async function file(url) {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: abort.signal,
    });
    if (!response.ok)
      throw Error(
        response.status === 401 || response.status === 403
          ? "Access denied"
          : "Preview failed",
      );
    const limit = 32 * 1024 * 1024;
    if (Number(response.headers.get("content-length")) > limit)
      throw Error("File too large");
    const reader = response.body.getReader(),
      chunks = [];
    let size = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > limit) throw Error("File too large");
        chunks.push(value);
      }
    } finally {
      await reader.cancel();
    }
    return new Blob(chunks, {
      type: response.headers.get("content-type") || "application/octet-stream",
    });
  }
  async function sheet(value) {
    selectedSheet = value;
    html = DOMPurify.sanitize(
      (await excelToTable(workbook.Sheets[value])).html,
    );
  }
  async function load() {
    const p = new URLSearchParams(location.search);
    const id = p.get("file_id"),
      terminal = p.get("terminal_id"),
      path = p.get("path"),
      chat = p.get("chat_id");
    if (
      !!id === !!terminal ||
      (id && !/^[\w-]+$/.test(id)) ||
      (terminal &&
        (!/^[\w-]+$/.test(terminal) ||
          !path ||
          path.includes("\0") ||
          (chat && !/^[\w-]+$/.test(chat))))
    )
      throw Error("Invalid document");
    token = localStorage.token || "";
    if (!token) throw Error("Sign in required");
    const session = await getSessionUser(token);
    if (!session?.id) throw Error("Sign in required");
    const page = Number(p.get("page"));
    targetPage = Number.isSafeInteger(page) && page > 0 ? page : null;
    if (id) {
      const meta = await fetch(`/api/v1/files/${encodeURIComponent(id)}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: abort.signal,
      });
      if (!meta.ok) throw Error("Access denied");
      name = (await meta.json()).filename;
      originalUrl = `/api/v1/files/${encodeURIComponent(id)}/content`;
    } else {
      name = path.split("/").filter(Boolean).at(-1) || "";
      const scope = chat ? `/chats/${encodeURIComponent(chat)}` : "";
      originalUrl = `/api/v1/terminals/${encodeURIComponent(terminal)}${scope}/files/view?path=${encodeURIComponent(path)}`;
    }
    const ext = name.split(".").at(-1)?.toLowerCase();
    if (!["pdf", "docx", "pptx", "xlsx", "xls"].includes(ext))
      throw Error("No preview available");
    let data;
    if (terminal && ["docx", "pptx"].includes(ext)) {
      try {
        const converted = await file(originalUrl + "&preview=true");
        if ((await converted.slice(0, 5).text()) === "%PDF-") {
          pdf = await converted.arrayBuffer();
          return;
        }
      } catch (e) {
        if (
          abort.signal.aborted ||
          e.message === "Access denied" ||
          e.message === "File too large"
        )
          throw e;
      }
    }
    data = await (await file(originalUrl)).arrayBuffer();
    if (ext === "pdf") pdf = data;
    else if (ext === "docx") docx = data;
    else if (ext === "pptx")
      slides = (
        await (await import("$lib/utils/pptxToHtml")).pptxToImages(data)
      ).images;
    else {
      workbook = await readExcelWorkbook(data);
      sheets = workbook.SheetNames;
      if (sheets.length) await sheet(sheets[0]);
    }
  }
  async function download() {
    try {
      const blob = await file(originalUrl);
      if (typeof window.conduitSaveDocument === "function") {
        await window.conduitSaveDocument(blob, name);
        return;
      }
      const url = URL.createObjectURL(blob),
        link = document.createElement("a");
      link.href = url;
      link.download = name;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      if (!abort.signal.aborted) error = e.message || "Download failed";
    }
  }
  onMount(() => {
    document.documentElement.classList.toggle(
      "dark",
      new URLSearchParams(location.search).get("theme") === "dark",
    );
    load()
      .catch((e) => {
        if (!abort.signal.aborted) error = e.message || "Preview failed";
      })
      .finally(() => (loading = false));
    return () => abort.abort();
  });
</script>

<svelte:head
  ><title>{name || "Document preview"} · Open WebUI</title></svelte:head
>
<main
  class="h-dvh flex flex-col bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100"
>
  <header class="flex shrink-0 items-center gap-3 border-b p-2 text-sm">
    <span class="shrink-0 font-semibold">Open WebUI</span><span
      class="min-w-0 flex-1 truncate">{name}</span
    >
    <button
      id="download"
      aria-label="Download"
      disabled={!name || loading}
      on:click={download}>↓</button
    >
  </header>
  <div class="flex-1 min-h-0 relative">
    {#if error}<p role="alert" class="p-4">{error}</p>
    {:else}<FilePreview
        selectedFile={name}
        fileLoading={loading}
        filePdfData={pdf}
        fileDocxData={docx}
        fileOfficeSlides={slides}
        fileOfficeHtml={html}
        excelSheetNames={sheets}
        selectedExcelSheet={selectedSheet}
        onSheetChange={sheet}
        {targetPage}
        readOnly={true}
      />{/if}
  </div>
</main>
