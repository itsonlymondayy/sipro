#!/usr/bin/env bash
# run_all_gates.sh — jalankan SEMUA guardrail SIPRO, tampilkan ringkasan.
# Exit !=0 bila ada gate GAGAL. Usage: bash scripts/run_all_gates.sh
cd "$(dirname "$0")/.."

GATES=(
  validate_compliance.py
  health_check.py
  verify_rbac.py
  verify_api_contract.py
  check_nav_map.py
  audit_endpoint_sweep.py
  verify_data_integrity.py
  ux_audit.py
  forensic_audit.py
  audit_forms_deep.py
  verify_business_invariants.py
  verify_ui_surfaces.py
  verify_31.py
  verify_32.py
  verify_33.py
  verify_34.py
  verify_35.py
  verify_36.py
  verify_37.py
  verify_settings.py
  verify_masterplan.py
  verify_39b.py
  verify_ia_v2.py
  verify_41.py
  verify_partner.py
  verify_rbac_ui.py
  verify_ads.py
  verify_analytics.py
  verify_budget_target.py
  verify_build_hub.py
)

fail=0
declare -a results
for g in "${GATES[@]}"; do
  if python3 "scripts/$g" > "/tmp/gate_${g}.log" 2>&1; then
    results+=("  PASS  $g")
  else
    results+=("  FAIL  $g")
    fail=1
  fi
done

echo ""
echo "==================== GATE SUMMARY ===================="
for r in "${results[@]}"; do echo "$r"; done
echo "======================================================"
if [ $fail -ne 0 ]; then
  echo "OVERALL: FAIL — detail gate yang gagal:"
  for g in "${GATES[@]}"; do
    if ! grep -qE "PASSED|Total temuan perlu tindakan: 0" "/tmp/gate_${g}.log" 2>/dev/null; then
      echo "----- $g -----"; tail -n 15 "/tmp/gate_${g}.log";
    fi
  done
  exit 1
fi
echo "OVERALL: PASS (${#GATES[@]} gates)"
