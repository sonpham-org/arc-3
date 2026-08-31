"""q350 Workbench Survey -- allocate samples while returning identity-bound sensor favors."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,LENS,EVIDENCE,DEBT,POLICY,BAD=4,10,9,14,6,11,5,7,15
LEVELS=[{"name":"Loaned Lens","budget":1,"plan":(1,4,5)},{"name":"Moved Sensor","budget":3,"plan":(2,4,1,2,5)},{"name":"Third Slice","budget":4,"plan":(3,4,1,2,3,5)},{"name":"Two Loans","budget":4,"plan":(1,4,2,4,1,5,2,5)},{"name":"Crossed Survey","budget":5,"plan":(2,4,3,4,1,2,5,3,5)},{"name":"Workbench Survey","budget":8,"plan":(1,4,2,4,3,4,1,3,5,2,5,1,5)}]
def advance(s,a,x):
 evidence,selected,cost,debt,policy=s;evidence=list(evidence);debt=list(debt)
 if a in (1,2,3):selected=a-1;item=(a,len(evidence)%4,(a+sum(debt)+len(evidence))%5);cost+=2 if item in evidence else 1;evidence.append(item)
 elif a==4:debt[selected]+=1;policy=(policy+selected+1)%5
 elif a==5:
  if not debt[selected]:return None
  debt[selected]-=1;policy=(sum(v for *_,v in evidence)+cost)%5
 if cost>x["budget"]:return None
 return tuple(evidence),selected,cost,tuple(debt),policy
def target(x):
 s=((),0,0,(0,0,0),0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i in range(3):x=8+i*18;f[8:31,x:x+14]=LENS;f[13+i*4:19+i*4,x+4:x+10]=TOOL-i;f[33:36,x:x+g.debt[i]*6]=DEBT
  for i,(*_,v) in enumerate(g.evidence[-6:]):f[39+i*3:41+i*3,8:11+v*10]=EVIDENCE
  f[56:59,8:11+g.policy*10]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q350(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q350",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.selected=self.cost=0;self.debt=(0,0,0);self.policy=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.selected,self.cost,self.debt,self.policy),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.selected,self.cost,self.debt,self.policy=s
  elif a==6:
   if (self.evidence,self.selected,self.cost,self.debt,self.policy)==self.target and not sum(self.debt):self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
