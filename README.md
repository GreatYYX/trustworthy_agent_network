# Trustworthy Agent Network

Large Language Model (LLM) agents are rapidly evolving from isolated assistants into collaborative ecosystems, where specialized agents communicate, delegate tasks, invoke tools, and coordinate autonomously. While this paradigm significantly expands the capabilities of AI systems, it also introduces fundamentally new trust challenges that cannot be addressed by existing single-agent safety techniques.

Our vision paper **"Trustworthy Agent Network: Trust in Agent Networks Must Be Baked In, Not Bolted On."** argues that trust in Agent-to-Agent (A2A) networks cannot be achieved through bolted-on safeguards alone, but must instead be built into the network architecture through principled design that makes trustworthy behavior an inherent property of the system.

Beyond this vision paper, this repository serves as a living index for research, resources, and discussions on trustworthy agent networks, bringing together emerging ideas, protocols, and future directions for building trustworthy multi-agent AI ecosystems.

## Resources

- Website: https://greatyyx.github.io/trustworthy_agent_network/
- Interactive guardrail demo: https://greatyyx.github.io/trustworthy_agent_network/demo.html
- Guardrail examples: [guardrail_examples](./guardrail_examples), including paired
  bolted-on failures and deterministic baked-in TAN transition experiments.

## Citation

```
@article{yao2026trustworthy,
  title={Trustworthy Agent Network: Trust in Agent Networks Must Be Baked In, Not Bolted On},
  author={Yao, Yixiang and Yao, Yuhang and Fan, Xinyi and Gao, Jiechao and Wang, Jie and Zhang, Minjia and Ravi, Srivatsan and Joe-Wong, Carlee},
  journal={arXiv preprint arXiv:2605.19035},
  year={2026}
}
```
