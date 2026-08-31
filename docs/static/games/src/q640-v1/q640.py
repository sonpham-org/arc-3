"""q640 Vault Sandbox -- preserve dual-ledger evidence while miniature vaults reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,SIM0,SIM1,A_ECHO,B_ECHO,RESET,COMMIT,BAD=4,11,9,14,12,6,10,13,15
LEVELS=[
 {"name":"One Reset","tests":(1,1,2),"resets":1},{"name":"Opposed Copies","tests":(2,2,1),"resets":1},
 {"name":"Persistent Ledgers","tests":(1,2,1,1),"resets":2},{"name":"Dual Sandbox","tests":(2,1,2,2),"resets":3},
 {"name":"Many Transfers","tests":(1,1,2,1,2),"resets":4},{"name":"Vault Sandbox","tests":(2,1,2,2,1,2),"resets":5}]
def choice_for(tests):
 score=[0,0]
 for a in tests:score[a-1]+=1 if a==1 else -1
 return (score[0]-score[1]+len(tests))%2
for x in LEVELS:x["choice"]=choice_for(x["tests"]);x["plan"]=x["tests"]+(3,)*x["resets"]+(4+x["choice"],)
def advance(s,a,x):
 sims,evidence,resets,committed=s;sims=[list(v) for v in sims];evidence=list(evidence)
 if a in (1,2):
  i=a-1;q=i;sims[i][q],sims[i][q+2]=sims[i][q+2],sims[i][q];evidence[q]+=1 if i==0 else -1
 elif a==3:sims=[[2,1,0,1],[1,2,1,0]];resets+=1
 elif a in (4,5):
  choice=a-4;correct=(evidence[0]-evidence[1]+len(x["tests"]))%2
  if resets<x["resets"] or choice!=correct:return None
  committed=(choice,tuple(evidence))
 return tuple(map(tuple,sims)),tuple(evidence),resets,committed
def target(x):
 s=(((2,1,0,1),(1,2,1,0)),(0,0),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT;f[8:33,8:29]=SIM0;f[8:33,35:56]=SIM1
  f[35:37,8:28]=A_ECHO;f[35:37,36:56]=B_ECHO
  for i,v in enumerate(g.evidence):f[38+i*7:42+i*7,8:8+abs(v)*9]=A_ECHO if i==0 else B_ECHO
  f[52:56,8:8+min(g.resets,6)*8]=RESET
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q640(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q640",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=((2,1,0,1),(1,2,1,0));self.evidence=(0,0);self.resets=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.resets,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.resets,self.committed=s
  elif a==6:
   if (self.sims,self.evidence,self.resets,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
