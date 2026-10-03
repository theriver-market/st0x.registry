#!/usr/bin/env python3
"""Generate river-basket-N.rain (N = 2..6 stocks) from the logic of river-basket
v2 (fork-proven 3 Oct). Same Rainlang per pair; only the number of slots changes."""
import pathlib

SUB = {'raindex': '0x22839F16281E67E5Fd395fAFd1571e820CbD46cB',
       'dia': '0xDf96DF297C963622C523F6d59e90b4C28CF61C21',
       'erc4626': '0xd69dC3d58a7C875117f9c7cecF4F1A7f3CA47254'}

def chain(sel, usdc_val, vals):
    # if(equal-to(sel usdc) U if(equal-to(sel t1) v1 ... vN))
    out = vals[-1]
    for i in range(len(vals) - 2, -1, -1):
        out = f"if(equal-to({sel} t{i+1}) {vals[i]} {out})"
    return f"if(equal-to({sel} usdc) {usdc_val} {out})"

def pick_src(n):
    # Subroutine: pick the value for token `sel` (usdc -> u, tK -> vK). One copy of the
    # if-chain instead of four keeps each source under the op limit for N >= 6.
    args = ' '.join(['sel', 'u'] + [f'v{i}' for i in range(1, n + 1)])
    return f"#pick\n{args}:,\n_: {chain('sel', 'u', [f'v{i}' for i in range(1, n + 1)])};\n"

def gen(n):
    sub = n >= 6  # 2..5 keep the fork-proven inline chains byte-for-byte
    ks = range(1, n + 1)
    toks = ['usdc'] + [f't{i}' for i in ks]
    io = '\n'.join(f'      - token: {t}' for t in toks)
    binds = '\n'.join(f'      t{i}: ${{order.inputs.{i}.token.address}}' for i in ks)
    fields = []
    for i in ks:
        fields += [f'        - binding: id{i}\n          name: DIA feed, stock {i}\n          show-custom-field: true']
    for i in ks:
        fields += [f'        - binding: w{i}\n          name: Target weight, stock {i} (fraction)\n          show-custom-field: true']
    fields += ['        - binding: budget\n          name: Budget (USDC deposited)\n          show-custom-field: true',
               '        - binding: band\n          name: Rebalance band (fraction)\n          show-custom-field: true\n          default: 0.02',
               '        - binding: fee\n          name: Rebalancer fee (fraction)\n          show-custom-field: true\n          default: 0.003',
               '        - binding: oracle-price-timeout\n          name: Oracle price max age (seconds)\n          show-custom-field: true\n          default: 10800',
               '        - binding: auction-start\n          name: First-buy auction start (fraction of oracle)\n          show-custom-field: true\n          default: 0.99',
               '        - binding: auction-cap\n          name: First-buy auction cap (fraction of oracle)\n          show-custom-field: true\n          default: 1.005',
               '        - binding: auction-seconds\n          name: Auction rise time (seconds)\n          show-custom-field: true\n          default: 3600']
    sel = '\n'.join(['        - key: usdc\n          name: USDC'] + [f'        - key: t{i}\n          name: Stock {i}' for i in ks])
    docs = '\n'.join(['#raindex-subparser !Raindex subparser.', '#dia-subparser !DiaWords subparser (dia-price).',
                      '#erc4626-subparser !ERC4626 words (erc4626-convert-to-assets).', '#usdc !USDC address.']
                     + [f'#t{i} !Stock token {i} (wt vault).' for i in ks]
                     + [f'#id{i} !DIA feed id for stock {i}.' for i in ks]
                     + [f'#w{i} !Target weight of stock {i}.' for i in ks]
                     + ['#budget !USDC budget used to size the initial buys.', '#band !Drift above which a rebalance is offered.',
                        '#fee !Discount to the oracle price paid to whoever rebalances.', '#oracle-price-timeout !Max oracle price age in seconds.',
                        '#auction-start !Funding buys start at oracle x this.', '#auction-cap !Funding buys never pay above oracle x this.',
                        '#auction-seconds !Seconds for the funding price to rise from start to cap.'])
    prices = '\n'.join([f'd{i} _: dia-price(id{i} oracle-price-timeout),' for i in ks]
                       + [f'p{i}: mul(d{i} erc4626-convert-to-assets(t{i} 1)),' for i in ks])
    pv = [f'p{i}' for i in ks]; wv = [f'w{i}' for i in ks]
    if sub:
        sel_lines = '\n'.join(f"{nm}: call<'pick>({s_} 1 {' '.join(vs)})," for nm, s_, vs in
                               [('p-out', 'out', pv), ('p-in', 'in', pv), ('w-out', 'out', wv), ('w-in', 'in', wv)])
    else:
        sel_lines = '\n'.join([f"p-out: {chain('out', '1', pv)},", f"p-in: {chain('in', '1', pv)},",
                                f"w-out: {chain('out', '1', wv)},", f"w-in: {chain('in', '1', wv)},"])
    return f"""version: 6

orders:
  base:
    raindex: base
    inputs:
{io}
    outputs:
{io}

scenarios:
  river-basket-{n}-base:
    raindex: base
    rainlang: base
    runs: 1
    bindings:
      raindex-subparser: {SUB['raindex']}
      dia-subparser: {SUB['dia']}
      erc4626-subparser: {SUB['erc4626']}
      usdc: ${{order.inputs.0.token.address}}
{binds}

deployments:
  base:
    order: base
    scenario: river-basket-{n}-base

builder:
  name: Portfolio ({n} stocks)
  description: >
    Holds {n} stock tokens at your target weights and keeps them there. Your USDC deposit
    buys each stock up to its share of the budget by Dutch auction around the onchain
    oracle price; then any stock that drifts above its weight is offered for one below
    its weight at oracle prices minus a small fee. Never sells into USDC.
  short-description: Your own basket of {n} stocks, kept at your weights.
  deployments:
    base:
      name: Base portfolio, {n} ST0x wt tokens
      description: {n} ST0x wt stock tokens priced by DIA oracle x the vault's live ratio.
      deposits:
        - token: usdc
      fields:
{chr(10).join(fields)}
      select-tokens:
{sel}
---
{docs}

#calculate-io
using-words-from raindex-subparser dia-subparser erc4626-subparser
{prices}
out: output-token(),
in: input-token(),
{sel_lines}
value-out: mul(output-vault-before() p-out),
value-in: mul(input-vault-before() p-in),
v-out: div(value-out w-out),
v-in: div(value-in w-in),
fund-usd: max(sub(mul(w-in budget) value-in) 0),
gap-usd: div(sub(v-out v-in) add(div(1 w-out) div(1 w-in))),
rebalance-usd: if(greater-than(v-out mul(v-in add(1 band))) gap-usd 0),
elapsed: sub(now() get(hash(order-hash() 1))),
auction: add(auction-start mul(sub(auction-cap auction-start) min(div(elapsed auction-seconds) 1))),
fund-io: div(1 mul(p-in auction)),
rebalance-io: mul(div(p-out p-in) sub(1 fee)),
max-output: if(equal-to(in usdc) 0 if(equal-to(out usdc) fund-usd div(rebalance-usd p-out))),
io: if(equal-to(out usdc) fund-io rebalance-io);

#handle-io
:set(hash(order-hash() 1) if(equal-to(output-token() usdc) now() get(hash(order-hash() 1))));

#handle-add-order
using-words-from raindex-subparser
:set(hash(order-hash() 1) now());
""" + ('\n' + pick_src(n) if sub else '')

root = pathlib.Path(__file__).resolve().parent.parent / 'src'
# N=6 inline exceeded the per-source op limit (SourceTotalOpsOverflow, 3 Oct); N>=6 use the #pick subroutine.
for n in range(2, 7):  # max = live DIA feeds (6 on 3 Oct)
    (root / f'river-basket-{n}.rain').write_text(gen(n))
    print('wrote', f'river-basket-{n}.rain')
