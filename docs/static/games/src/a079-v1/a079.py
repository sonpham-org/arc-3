"""a079 Crank Slider -- exploit nonlinear slider speed at chosen phases."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SHOP,WHEEL,CRANK,ROD,SLIDER,OBJECT,CONTACT,SPEED,BAD=7,8,9,12,14,10,11,13,6,15
LOOKUP=(0,2,5,8,10,11,10,8,5,2,0,1)
LEVELS=[
 {"name":"Rotate Crank","seq":(1,)},{"name":"Reverse Phase","seq":(1,2)},
 {"name":"Change Radius","seq":(3,1,1)},{"name":"Timed Contact","seq":(1,1,4,2,1)},
 {"name":"Two Speeds","seq":(3,1,4,1,1,4,2)},{"name":"Crank Slider","seq":(1,3,1,4,2,1,1,4,3,1)},
]
def advance(s,a):
 phase,radius,slider,objects,speeds,contacts,history,snapshot=s;ob=list(objects)
 old=slider
 if a==1:phase=(phase+1)%12;history=(history+(1,))[-8:]
 elif a==2:phase=(phase-1)%12;history=(history+(2,))[-8:]
 elif a==3:radius=1+radius%3;history=(history+(3,))[-8:]
 if a in (1,2,3):slider=min(15,LOOKUP[phase]+radius*2)
 elif a==4:
  speed=abs(slider-old)+radius;ob[contacts%2]=(ob[contacts%2]+speed)%12;speeds=(speeds+(speed,))[-6:];contacts=(contacts+1)%6;history=(history+(4,))[-8:]
 elif a==5:snapshot=(phase,radius,slider,tuple(ob),speeds,contacts,history)
 return phase,radius,slider,tuple(ob),speeds,contacts,history,snapshot
for x in LEVELS:
 s=(0,1,LOOKUP[0]+2,(0,6),(),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP;f[15:43,8:32]=WHEEL;f[19:39,12:28]=SHOP
  cx,cy=20,29;dx=(0,3,6,8,9,8,6,3,0,-3,-6,-8)[g.phase];dy=(9,8,6,3,0,-3,-6,-8,-9,-8,-6,-3)[g.phase];f[cy+dy-3:cy+dy+4,cx+dx-3:cx+dx+4]=CRANK
  sx=34+g.slider
  for i in range(17):x=cx+dx+(sx-cx-dx)*i//16;y=cy+dy+(29-cy-dy)*i//16;f[y:y+2,x:x+2]=ROD
  f[24:36,sx:sx+8]=SLIDER
  for i,p in enumerate(g.objects):x=8+p*4;f[46+i*7:52+i*7,x:x+6]=OBJECT
  for i,v in enumerate(g.speeds):f[8:11,36+i*4:39+i*4]=SPEED
  f[39:44,47:57]=CONTACT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A079(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a079",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase,self.radius,self.slider,self.objects,self.speeds,self.contacts,self.history,self.snapshot=(0,1,LOOKUP[0]+2,(0,6),(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phase,self.radius,self.slider,self.objects,self.speeds,self.contacts,self.history,self.snapshot=advance((self.phase,self.radius,self.slider,self.objects,self.speeds,self.contacts,self.history,self.snapshot),a)
  elif a==6:
   if (self.phase,self.radius,self.slider,self.objects,self.speeds,self.contacts,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
