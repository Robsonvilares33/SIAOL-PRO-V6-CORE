(() => {
  const card = document.getElementById("mcp-connection-card");
  if (!card) return;

  // A interface informa apenas o estado de configuração. Nunca faz chamadas
  // automáticas ao servidor nem lê/exibe tokens ou credenciais.
  card.dataset.connectionState = "not-configured";
})();
