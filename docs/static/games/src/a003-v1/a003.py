"""a003 False Floor Clinic -- infer a cracked support from propagated deformation fields."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLINIC,TILE,BEAM,WEIGHT,SAG,PROBE,GOAL,BAD=2,10,8,14,11,12,6,13,15
LEVELS=[{"name":"Light Probe","seq":(1,3)},{"name":"Moved Weight","seq":(2,3)},{"name":"Field Contrast","seq":(1,2,3)},{"name":"Beam Rotation","seq":(4,2,1,3)},{"name":"Latent Crack","seq":(2,3,1,4,2,1,3)},{"name":"False Floor Clinic","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 probe,load,orientation,crack,evidence,brace=s
 if a==1:probe=(probe-1)%9;load=min(3,load+1)
 elif a==2:probe=(probe+2)%9;load=max(1,load-1)
 elif a==3:field=tuple(max(0,5-(abs((i%3)-(crack%3))+abs((i//3)-(crack//3)))+load+orientation)%6 for i in range(9));evidence=evidence+((probe,load,orientation,field),)
 elif a==4:orientation^=1;probe=(probe+3)%9
 elif a==5:brace=(crack,probe,load,orientation,evidence[-4:])
 return probe,load,orientation,crack,evidence,brace
for x in LEVELS:
 s=(4,1,0,7,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CLINIC;field=g.evidence[-1][3] if g.evidence else (0,)*9
  for i,v in enumerate(field):x=8+(i%3)*17;y=8+(i//3)*10;f[y:y+8,x:x+14]=TILE;f[y+6-v:y+8,x+2:x+12]=SAG;f[y:y+2,x:x+14]=BEAM
  px=8+(g.probe%3)*17;py=8+(g.probe//3)*10;f[py+2:py+6,px+5:px+9]=WEIGHT
  for i,_ in enumerate(g.evidence[-4:]):f[43:49,8+i*12:17+i*12]=PROBE
  if g.brace:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A003(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a003",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.probe=4;self.load=1;self.orientation=0;self.crack=7;self.evidence=();self.brace=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.probe,self.load,self.orientation,self.crack,self.evidence,self.brace=advance((self.probe,self.load,self.orientation,self.crack,self.evidence,self.brace),a)
  elif a==6:
   if (self.probe,self.load,self.orientation,self.crack,self.evidence,self.brace)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
