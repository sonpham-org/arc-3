"""q760 Vault Obligation -- repay two quantity debts to causal identities after swaps."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,PANE0,PANE1,A_ECHO,B_ECHO,DEBT,REPAID,BAD=9,11,10,14,12,6,13,8,15
LEVELS=[
 {"name":"First Debt","borrows":(1,),"swaps":0},{"name":"Second Ledger","borrows":(1,2),"swaps":0},
 {"name":"Identity Swap","borrows":(1,2),"swaps":1},{"name":"Repeated Borrow","borrows":(1,1,2),"swaps":2},
 {"name":"Long Obligation","borrows":(1,2,2,1),"swaps":3},{"name":"Vault Obligation","borrows":(1,1,2,2,1),"swaps":4}]
def plan_for(x):
 slots=[0,1];debt=[False,False]
 for a in x["borrows"]:debt[slots[0] if a==1 else slots[1]]=True
 for _ in range(x["swaps"]):slots.reverse()
 repays=tuple(4+slots.index(i) for i in range(2) if debt[i]);return x["borrows"]+(3,)*x["swaps"]+repays
for x in LEVELS:x["plan"]=plan_for(x)
def advance(s,a,x):
 slots,holdings,player,debts,repaid=s;slots=list(slots);h=[list(v) for v in holdings];p=list(player);d=[list(v) for v in debts];repaid=list(repaid)
 if a==1:
  who=slots[0]
  if not h[who][0]:return None
  h[who][0]-=1;p[0]+=1;d[who][0]+=1
 elif a==2:
  who=slots[1]
  if not h[who][1]:return None
  h[who][1]-=1;p[1]+=1;d[who][1]+=1
 elif a==3:slots.reverse()
 elif a in (4,5):
  who=slots[a-4]
  if not sum(d[who]):return None
  for q in range(2):p[q]-=d[who][q];h[who][q]+=d[who][q];d[who][q]=0
  repaid.append(who)
 return tuple(slots),tuple(map(tuple,h)),tuple(p),tuple(map(tuple,d)),tuple(repaid)
def target(x):
 s=((0,1),((3,2),(2,3)),(0,0),((0,0),(0,0)),())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT;f[8:34,8:29]=PANE0;f[8:34,35:56]=PANE1
  for pos,who in enumerate(g.slots):
   x=11+pos*27;a,b=g.holdings[who];f[13:18,x:x+a*4]=A_ECHO;f[22:27,x:x+b*4]=B_ECHO
  f[39:43,8:8+g.player[0]*7]=A_ECHO;f[46:50,8:8+g.player[1]*7]=B_ECHO;f[53:57,8:28]=DEBT
  if g.repaid:f[54:59,39:56]=REPAID
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q760(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q760",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.holdings=((3,2),(2,3));self.player=(0,0);self.debts=((0,0),(0,0));self.repaid=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.holdings,self.player,self.debts,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.holdings,self.player,self.debts,self.repaid=s
  elif a==6:
   if (self.slots,self.holdings,self.player,self.debts,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
