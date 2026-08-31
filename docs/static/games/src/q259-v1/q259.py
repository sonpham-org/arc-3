"""q259 Monsoon Pact -- infer a rain-seed convention before a joint-cycle commitment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,OFFER,REPLY,CYCLE,CHOICE,BAD=1,10,9,14,6,4,11,7,15
LEVELS=[{"name":"Fair Shower","rule":1,"periods":(2,2),"plan":(4,1,5)},{"name":"Recent Front","rule":2,"periods":(3,3),"plan":(4,1,4,5)},{"name":"Reciprocal Rain","rule":3,"periods":(2,2),"plan":(4,1,4,4,5)},{"name":"Unequal Pact","rule":2,"periods":(2,3),"plan":(4,1,2,4,3,1,5)},{"name":"Long Courtesy","rule":3,"periods":(3,4),"plan":(4,1,2,3,4,1,2,3,4,1,2,3,5)},{"name":"Monsoon Pact","rule":1,"periods":(4,5),"plan":(4,1,2,3,1,2,3,1,2,3,1,2,3,1,2,3,1,2,3,1,5)}]
def advance(s,a,x):
 evidence,last,choice,pa,pb=s;evidence=list(evidence)
 if a in (1,2,3,4):
  if a==4:choice=(choice+1)%4
  else:evidence.append((a,(x["rule"]*a+last+pa+pb)%4));last=a
  pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or choice!=x["rule"] or not evidence:return None
 return tuple(evidence),last,choice,pa,pb
def target(x):
 s=((),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i in range(3):x=8+i*18;f[8:30,x:x+14]=CLOUD;f[13+i*4:19+i*4,x+4:x+10]=RAIN-i
  for i,(_,v) in enumerate(g.evidence[-6:]):f[34+i*3:36+i*3,8:11+v*11]=REPLY
  f[31:33,8:20]=OFFER;f[53:56,8:11+g.choice*12]=CHOICE;f[57:60,40:56]=CYCLE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q259(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q259",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.last=self.choice=self.pa=self.pb=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.last,self.choice,self.pa,self.pb),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.last,self.choice,self.pa,self.pb=s
  elif a==6:
   if (self.evidence,self.last,self.choice,self.pa,self.pb)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
