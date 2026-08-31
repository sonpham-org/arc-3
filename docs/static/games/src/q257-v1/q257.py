"""q257 Spectrum Pact -- infer one convention across geometry and agent domains."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PANE,PACKET,OFFER,REPLY,DOMAIN,CHOICE,BAD=1,10,9,14,6,4,11,7,15
LEVELS=[{"name":"Fair Geometry","rule":1,"plan":(1,5)},{"name":"Recent Agent","rule":2,"plan":(2,4,1,5,5)},{"name":"Reciprocal Packet","rule":3,"plan":(1,3,4,2,5,5,5)},{"name":"Relational Pact","rule":2,"plan":(3,1,4,2,5,5)},{"name":"Domain Return","rule":3,"plan":(2,4,1,3,2,5,5,5)},{"name":"Spectrum Pact","rule":1,"plan":(1,4,3,2,4,1,5)}]
def response(rule,a,last,domain):return (rule*a+last+domain)%4
def advance(s,a,x):
 evidence,last,domain,choice=s;evidence=list(evidence)
 if a in (1,2,3):evidence.append((domain,a,response(x["rule"],a,last,domain)));last=a
 elif a==4:domain=1-domain
 elif a==5:choice=(choice+1)%4
 return tuple(evidence),last,domain,choice
def target(x):
 s=((),0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i in range(3):x=8+i*18;f[9:32,x:x+14]=PANE;f[15+i*4:22+i*4,x+4:x+10]=PACKET-i
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[36+i*3:38+i*3,8:11+v*11]=REPLY
  f[33:35,8:20]=OFFER;f[53:56,8:11+g.domain*22]=DOMAIN;f[57:60,8:11+g.choice*12]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q257(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q257",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.last=self.domain=self.choice=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.evidence,self.last,self.domain,self.choice=advance((self.evidence,self.last,self.domain,self.choice),a,x)
  elif a==6:
   if (self.evidence,self.last,self.domain,self.choice)==self.target and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
