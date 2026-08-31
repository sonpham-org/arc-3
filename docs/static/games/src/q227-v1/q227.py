"""q227 Spectrum Veil -- schedule attention while one relation transfers across domains."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PANE,PACKET,FOCUS,DOMAIN,RELATION,ANCHOR,BAD=0,10,9,14,6,11,4,7,15
LEVELS=[{"name":"Geometric Pane","plan":(1,4)},{"name":"Agent Packet","plan":(2,1,4)},{"name":"Shared Relation","plan":(3,5,4,1)},{"name":"Cross-Domain Veil","plan":(1,4,2,5,3)},{"name":"Relational Return","plan":(2,5,3,4,1,5)},{"name":"Spectrum Veil","plan":(3,4,1,5,2,4,3,5)}]
def advance(s,a):
 packets,focus,domain,relation,anchors=s;packets=list(packets);anchors=list(anchors)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:packets[i]=(packets[i]+relation+i+domain+1)%5
 elif a==4:domain=1-domain;packets=[(relation-v)%5 for v in packets]
 elif a==5:anchors.append((domain,tuple((packets[i]-packets[(i+1)%3])%5 for i in range(3))));relation=(relation+sum(packets)+domain)%5
 return tuple(packets),focus,domain,relation,tuple(anchors)
def target(x):
 s=((0,2,4),0,0,1,())
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i,v in enumerate(g.packets):x=8+i*18;f[9:38,x:x+14]=PANE;f[14+v*5:21+v*5,x+4:x+10]=PACKET-(i if not g.domain else (2-i))
  f[7:10,8+g.focus*18:22+g.focus*18]=FOCUS;f[43:46,8:11+g.domain*22]=DOMAIN;f[50:53,8:11+g.relation*10]=RELATION;f[56:59,8:11+len(g.anchors)*10]=ANCHOR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q227(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q227",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.packets=(0,2,4);self.focus=self.domain=0;self.relation=1;self.anchors=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.packets,self.focus,self.domain,self.relation,self.anchors=advance((self.packets,self.focus,self.domain,self.relation,self.anchors),a)
  elif a==6:
   if (self.packets,self.focus,self.domain,self.relation,self.anchors)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
