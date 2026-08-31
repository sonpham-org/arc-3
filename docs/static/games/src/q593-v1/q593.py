"""q593 Ember Grammar -- compose grouping and spatial relays under one effort budget."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,GLYPH,GROUP,RELATION,RELAY,VESSEL,HEAT,RESOURCE,BAD=12,1,7,4,9,11,6,2,10,15
LEVELS=[
 {"name":"Grouped Relay","plan":(1,3),"budget":4},{"name":"Relative Relay","plan":(2,3),"budget":4},
 {"name":"Two-Part Message","plan":(1,2,3),"budget":5},{"name":"Move the Vessel","plan":(1,2,3,4),"budget":6},
 {"name":"Fire the Phrase","plan":(4,1,2,3,5),"budget":7},{"name":"Ember Grammar","plan":(1,2,4,3,4,5,3),"budget":9}]
def advance(s,a,x):
 group,relation,relay,vessel,heat,resource=s
 if resource<=0:return None
 resource-=1
 if a==1:group=(group+1)%4
 elif a==2:relation=(relation+1)%3
 elif a==3:relay=(relay+group+relation+1)%5
 elif a==4:vessel=(vessel+relay+relation+1)%6
 elif a==5:heat=(heat+vessel+group+1)%7
 return group,relation,relay,vessel,heat,resource
def target(x):
 s=(0,0,0,0,0,x["budget"])
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[3:61,3:61]=KILN;f[7:22,7:57]=GLYPH
  for i,v in enumerate((g.group,g.relation,g.relay)):f[10:18,9+i*16:13+i*16+v*2]=GROUP+i*2
  f[28:40,7:20+g.vessel*6]=VESSEL;f[43:49,7:10+g.heat*7]=HEAT;f[53:57,7:7+g.resource*5]=RESOURCE
  f[24:53,55:58]=RELAY
  if g.bad:f[0:3,17:47]=BAD
  return f
class Q593(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q593",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.group=self.relation=self.relay=self.vessel=self.heat=0;self.resource=self.cfg["budget"]
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.group,self.relation,self.relay,self.vessel,self.heat,self.resource),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.group,self.relation,self.relay,self.vessel,self.heat,self.resource=s
  elif a==6:
   if (self.group,self.relation,self.relay,self.vessel,self.heat,self.resource)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
