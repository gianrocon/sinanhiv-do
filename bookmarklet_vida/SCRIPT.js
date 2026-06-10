javascript:(function(){
  const g=s=>{const el=document.querySelector('[id$="'+s+'"]');if(!el)return'Não encontrado';return(el.value!==undefined&&el.value!==''?el.value:el.innerText).trim()||'Não encontrado';};
  const pront=g('txtNumeroProntuario')||g('lblProntuario');
  const c='Nome: '+g('lblNome')+' | SUS: '+g('lblCartao')+' | Prontuário: '+pront+' | Nascimento: '+g('lblDataNascimento')+' | Mãe: '+g('lblNomeMae');
  navigator.clipboard.writeText(c).then(()=>{const d=document.createElement('div');d.innerText='Dados copiados!';d.style.cssText='position:fixed;top:20px;right:20px;background:#28a745;color:#fff;padding:15px;z-index:99999;border-radius:5px;box-shadow:0 2px 10px rgba(0,0,0,0.3);font-family:sans-serif;';document.body.appendChild(d);setTimeout(()=>d.remove(),2000);}).catch(e=>alert('Erro ao copiar: '+e));
})();