"""q260 Workbench Pact -- infer a convention while favors remain bound to helpers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,OFFER,REPLY,DEBT,CHOICE,BAD=1,10,9,14,6,4,11,7,15
LEVELS=[{"name":"One Favor","rule":1,"plan":(1,4,5)},{"name":"Moved Offer","rule":2,"plan":(2,4,1,2,5)},{"name":"Third Helper","rule":3,"plan":(3,4,1,2,3,5)},{"name":"Paired Courtesy","rule":2,"plan":(1,4,2,4,1,5,2,5)},{"name":"Reciprocal Debt","rule":3,"plan":(2,4,3,4,1,2,5,3,5)},{"name":"Workbench Pact","rule":1,"plan":(1,4,2,4,3,4,3,5,2,5,1,5)}]
def advance(s,a,x):
 evidence,selected,last,debt,choice=s;evidence=list(evidence);debt=list(debt)
 if a in (1,2,3):selected=a-1;reply=(x["rule"]*a+last+sum(debt))%4;evidence.append((selected,reply));last=reply;choice=(choice+reply)%4
 elif a==4:debt[selected]+=1;choice=(choice+x["rule"]+selected)%4
 elif a==5:
  if not debt[selected]:return None
  debt[selected]-=1
 return tuple(evidence),selected,last,tuple(debt),choice
def target(x):
 s=((),0,0,(0,0,0),0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i in range(3):x=8+i*18;f[8:31,x:x+14]=FIXTURE;f[13+i*4:19+i*4,x+4:x+10]=TOOL-i;f[33:36,x:x+g.debt[i]*6]=DEBT
  for i,(_,v) in enumerate(g.evidence[-6:]):f[39+i*3:41+i*3,8:11+v*11]=REPLY
  f[36:38,8:20]=OFFER;f[56:59,8:11+g.choice*11]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q260(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q260",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.selected=self.last=0;self.debt=(0,0,0);self.choice=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.selected,self.last,self.debt,self.choice),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.selected,self.last,self.debt,self.choice=s
  elif a==6:
   if (self.evidence,self.selected,self.last,self.debt,self.choice)==self.target and not sum(self.debt):self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
