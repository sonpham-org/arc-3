"""q252 Semaphore Pact -- infer one convention from offers in two miniature signal courts."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,MAST,FLAG,OFFER,MINI,EVIDENCE,CHOICE,BAD=10,1,12,14,6,15,11,9,8
LEVELS=[{"name":"Fair Flag","rule":1,"a":(1,),"b":(2,)},{"name":"Recent Beam","rule":2,"a":(2,1),"b":(3,)},{"name":"Reciprocal Mast","rule":3,"a":(1,3),"b":(2,1)},{"name":"Two Courts","rule":2,"a":(3,2,1),"b":(1,3)},{"name":"Joint Policy","rule":3,"a":(2,1,3),"b":(3,1,2)},{"name":"Semaphore Pact","rule":1,"a":(1,2,3,1),"b":(2,3,1,2)}]
def response(rule,mini,a,last):return (rule+a+last+mini*(rule+1))%4
def expected(x):
 out=[];last=0
 for mini,seq in ((0,x["a"]),(1,x["b"])):
  for a in seq:out.append((mini,a,response(x["rule"],mini,a,last)));last=a
 return tuple(out)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=YARD
  for i in range(3):x=9+i*18;f[10:42,x:x+3]=MAST;f[12+i*7:20+i*7,x+3:x+13]=FLAG
  f[7:10,8+g.mini*25:28+g.mini*25]=MINI
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[43+i*2:45+i*2,7:7+v*12]=EVIDENCE
  f[56:59,8:8+g.choice*13]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q252(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mini=0;self.last=0;self.evidence=[];self.choice=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q252",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mini=0;self.last=0;self.evidence=[];self.choice=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.evidence.append((self.mini,a,response(x["rule"],self.mini,a,self.last)));self.last=a
  elif a==4:self.mini=1-self.mini
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   if tuple(self.evidence)==expected(x) and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
