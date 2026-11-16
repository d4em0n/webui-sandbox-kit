<script>
  import { setContext } from "svelte";
  import i18n, { initI18n } from "$lib/i18n";
  import "$webui/tailwind.css";
  import "$webui/app.css";
  setContext("i18n", i18n);
  const ready = initI18n();
</script>

{#await ready then}<slot />{/await}

<style>
  :global(html),
  :global(body) {
    height: 100%;
    margin: 0;
  }
  :global(body) {
    overflow: hidden;
  }
</style>
