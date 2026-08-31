"""q745 Alloy Obligation -- repay causal identities after swaps and frame rotation."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,IDENTITY,DEBT,REWARD,FRAME,REPAY,BAD=11,1,8,6,2,13,9,4,15
LEVELS=[
 {"name":"Direct Return","plan":(1,5)},{"name":"Rotated Creditor","plan":(2,4,5)},
 {"name":"Swapped Identity","plan":(1,3,4,5)},{"name":"Full Frame Return","plan":(1,4,4,4,5)},
 {"name":"Two Creditors","plan":(1,2,4,5,4,4,5)},{"name":"Alloy Obligation","plan":(1,3,4,5,2,4,5)}]
def advance(s,a,x):
 slots,debts,reward,origin,rotation,repaid=s;slots=list(slots);debts=list(debts);repaid=list(repaid)
 if a in (1,2):
  who=slots[(rotation+a-1)%3];debts[who]+=1;reward+=3
 elif a==3:
  i=rotation;j=(rotation+1)%3;slots[i],slots[j]=slots[j],slots[i]
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%3
 elif a==5:
  who=slots[rotation]
  if debts[who]<=0:return None
  debts[who]-=1;reward-=1;repaid.append(who)
 return tuple(slots),tuple(debts),reward,origin,rotation,tuple(repaid)
def target(x):
 s=((0,1,2),(0,0,0),0,0,0,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for screen in range(3):
   x=8+screen*17;physical=(g.rotation+screen)%3;who=g.slots[physical];f[9:35,x:x+13]=LANE+screen%2;f[14:25,x+2:x+11]=IDENTITY+who*2;f[29:32,x+2:x+2+g.debts[who]*7]=DEBT
  f[41:45,8:8+g.reward*4]=REWARD;f[48:51,8:8+g.origin*8]=FRAME;f[53:56,8:8+len(g.repaid)*8]=REPAY
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q745(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q745",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1,2);self.debts=(0,0,0);self.reward=self.origin=self.rotation=0;self.repaid=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debts,self.reward,self.origin,self.rotation,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debts,self.reward,self.origin,self.rotation,self.repaid=s
  elif a==6:
   if (self.slots,self.debts,self.reward,self.origin,self.rotation,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
